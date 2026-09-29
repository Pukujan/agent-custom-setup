"""APUS OpenJev v1 over a local Ollama server.

Prompt layout follows the official APUS OpenJev GGUF example contract:
https://huggingface.co/apus-ailab/APUS-OpenJev-v1-4B-GGUF
Ollama exposes only top-20 log-probabilities, so distributions are marked
incomplete whenever any candidate label is absent.
"""
from __future__ import annotations

import ipaddress
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from local_decision_client import LocalEndpointError, _NoRedirect, _is_local_host


LABELS = "ABCDEFGHIJKLMNOP"
NO_THINK_CHAT = "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


@dataclass(frozen=True)
class OllamaOpenJevConfig:
    lane_id: str
    base_url: str
    model_id: str
    expected_digest: Optional[str] = None
    allow_tailnet_ips: Optional[List[str]] = None
    timeout_s: float = 600.0


class OpenJevOllamaClient:
    def __init__(self, config: OllamaOpenJevConfig) -> None:
        parsed = urllib.parse.urlsplit(config.base_url)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise LocalEndpointError("local_http_endpoint_required")
        if parsed.query or parsed.fragment or not _is_local_host(parsed.hostname, config.allow_tailnet_ips or []):
            raise LocalEndpointError("endpoint_not_loopback_or_allowlisted_tailnet")
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _request(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=self.config.timeout_s) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LocalEndpointError(f"local_request_failed:{type(exc).__name__}") from exc
        if not isinstance(value, dict):
            raise LocalEndpointError("invalid_response_root")
        return value

    def inventory(self) -> Dict[str, Any]:
        value = self._request("/api/tags")
        models = value.get("models")
        if not isinstance(models, list):
            raise LocalEndpointError("invalid_ollama_inventory")
        selected = [row for row in models if isinstance(row, dict) and row.get("name") == self.config.model_id]
        if not selected:
            raise LocalEndpointError("configured_model_not_in_local_inventory")
        if self.config.expected_digest and selected[0].get("digest") != self.config.expected_digest:
            raise LocalEndpointError("model_digest_mismatch")
        return {"models": models, "selected": selected[0]}

    @staticmethod
    def _render_prompt(state: Any, primitive: str, instructions: str, criteria: List[Dict[str, str]]) -> tuple[str, Dict[str, str]]:
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("instructions_required")
        if primitive not in {"choice", "noul", "score_level"}:
            raise ValueError("unsupported_primitive")
        if not isinstance(criteria, list) or not 2 <= len(criteria) <= len(LABELS):
            raise ValueError("criteria_must_contain_2_to_16_candidates")
        ids: List[str] = []
        clean: List[Dict[str, str]] = []
        for candidate in criteria:
            if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str) or not candidate["id"].strip() or not isinstance(candidate.get("description"), str) or not candidate["description"].strip():
                raise ValueError("invalid_candidate")
            ids.append(candidate["id"])
            clean.append({"id": candidate["id"], "description": candidate["description"]})
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_candidate_ids")
        if primitive != "choice" and clean != [
            {"id": "yes", "description": "The stated proposition is true."},
            {"id": "no", "description": "The stated proposition is false."},
        ]:
            raise ValueError("binary_primitive_requires_canonical_yes_no_criteria")
        labels = LABELS[:len(clean)]
        mapping = dict(zip(labels, ids))
        state_text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt = "Shared state:\n" + state_text + "\n\n"
        task = {
            "primitive": primitive,
            "instructions": instructions,
            "criteria": [{"label": label, "description": item["description"]} for label, item in zip(labels, clean)],
        }
        prompt += json.dumps(task, ensure_ascii=False, sort_keys=True)
        prompt += "\nReturn only the selected letter: " + ", ".join(labels) + ".\nAnswer:"
        return NO_THINK_CHAT.format(prompt=prompt), mapping

    def decide(self, *, state: Any, instructions: str, criteria: List[Dict[str, str]], primitive: str = "choice") -> Dict[str, Any]:
        prompt, mapping = self._render_prompt(state, primitive, instructions, criteria)
        data = self._request("/api/generate", {
            "model": self.config.model_id,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "think": False,
            "logprobs": True,
            "top_logprobs": 20,
            "options": {"temperature": 0, "num_predict": 1, "num_ctx": 9216},
        })
        try:
            position, = data["logprobs"]
            distribution_rows = position["top_logprobs"]
            logprobs = {str(row["token"]): float(row["logprob"]) for row in distribution_rows}
        except (KeyError, TypeError, ValueError) as exc:
            raise LocalEndpointError("openjev_logprob_schema_missing") from exc
        labels = list(mapping)
        complete = all(label in logprobs for label in labels)
        result: Dict[str, Any] = {
            "lane_id": self.config.lane_id,
            "model": self.config.model_id,
            "primitive": primitive,
            "distribution_complete": complete,
            "distribution_semantics": "candidate-normalized top-20 logprobs; uncalibrated",
        }
        if complete:
            peak = max(logprobs[label] for label in labels)
            weights = {label: math.exp(logprobs[label] - peak) for label in labels}
            total = sum(weights.values())
            probabilities = {mapping[label]: weight / total for label, weight in weights.items()}
            result["probabilities"] = probabilities
            selected = max(probabilities, key=probabilities.get)
        else:
            result["distribution_omission_count"] = sum(label not in logprobs for label in labels)
            selected_label = str(data.get("response", "")).strip()
            if selected_label not in mapping:
                raise LocalEndpointError("openjev_answer_not_candidate_label")
            selected = mapping[selected_label]
        result["choice"] = selected if primitive == "choice" else None
        result["answer"] = selected
        return result

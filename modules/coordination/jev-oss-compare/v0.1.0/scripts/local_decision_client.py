"""Strict client for explicitly local System-One-compatible decision servers.

This module intentionally contains no Jev/OpenRouter or hosted fallback code.
"""
from __future__ import annotations

import ipaddress
import json
import math
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class LocalEndpointError(RuntimeError):
    pass


def _is_local_host(host: str, allow_ips: Optional[List[str]] = None) -> bool:
    lowered = host.lower().strip("[]")
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(lowered)
        if ip.is_loopback:
            return True
        tailnet = ipaddress.ip_network("100.64.0.0/10")
        if ip in tailnet and lowered in (allow_ips or []):
            return True
        return False
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise LocalEndpointError("redirect_refused")


@dataclass(frozen=True)
class LocalModelConfig:
    lane_id: str
    base_url: str
    model_id: str
    expected_revision: Optional[str] = None
    expected_base: Optional[str] = None
    expected_response_model: Optional[str] = None
    expected_route_model: Optional[str] = None
    expected_route_repo: Optional[str] = None
    allow_tailnet_ips: Optional[List[str]] = None
    api_key_env: Optional[str] = None
    timeout_s: float = 30.0
    confidence_definition: str = "provider_defined; record raw fields"


class LocalDecisionClient:
    def __init__(self, config: LocalModelConfig) -> None:
        self.config = config
        parsed = urllib.parse.urlsplit(config.base_url)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise LocalEndpointError("local_http_endpoint_required")
        if parsed.query or parsed.fragment:
            raise LocalEndpointError("endpoint_query_or_fragment_forbidden")
        if not _is_local_host(parsed.hostname, config.allow_tailnet_ips or []):
            raise LocalEndpointError("endpoint_not_loopback_or_allowlisted_tailnet")
        self.base_url = config.base_url.rstrip("/")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key_env:
            key = os.environ.get(self.config.api_key_env, "").strip()
            if not key:
                raise LocalEndpointError("configured_local_api_key_missing")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers=self._headers(),
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.config.timeout_s) as response:
                value = json.loads(response.read().decode("utf-8"))
        except LocalEndpointError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LocalEndpointError(f"local_request_failed:{type(exc).__name__}") from exc
        if not isinstance(value, dict):
            raise LocalEndpointError("invalid_response_root")
        return value

    def inventory(self) -> Dict[str, Any]:
        """Read exact local server/model inventory without running inference."""
        try:
            response = self._request("GET", "/v1/models")
        except LocalEndpointError as first:
            # Some local Laya builds report health/checkpoint identity here.
            try:
                health = self._request("GET", "/health")
            except LocalEndpointError:
                raise first
            if not isinstance(health, dict):
                raise first
            models = health.get("models") or [health.get("model")]
            normalized = []
            for model in models:
                if isinstance(model, str):
                    normalized.append({"id": model})
                elif isinstance(model, dict):
                    normalized.append(model)
            if health.get("model") and not normalized:
                normalized = [{"id": str(health["model"])}]
            if not normalized and isinstance(health.get("loaded"), list):
                revisions = health.get("revisions") if isinstance(health.get("revisions"), dict) else {}
                devices = health.get("checkpoint_devices") if isinstance(health.get("checkpoint_devices"), dict) else {}
                normalized = [
                    {"id": str(model), "revision": revisions.get(model), "device": devices.get(model)}
                    for model in health["loaded"]
                ]
            response = {"data": normalized}
        data = response.get("data") or response.get("models") or []
        models: List[Dict[str, Any]] = []
        for row in data:
            if isinstance(row, str):
                models.append({"id": row})
            elif isinstance(row, dict):
                normalized = {
                    "id": row.get("id") or row.get("model") or row.get("name"),
                    "model": row.get("model") or row.get("name") or row.get("id"),
                    "revision": row.get("revision") or row.get("run"),
                    "base": row.get("base"),
                    "backend": row.get("backend"),
                    "device": row.get("device"),
                    "dtype": row.get("dtype"),
                    "temperature": row.get("temperature"),
                }
                models.append({k: v for k, v in normalized.items() if v is not None})
        exact = [m for m in models if self.config.model_id in {m.get("id"), m.get("model")}]
        if not exact:
            raise LocalEndpointError("configured_model_not_in_local_inventory")
        if self.config.expected_revision:
            revisions = {m.get("revision") for m in exact if m.get("revision")}
            if not revisions or self.config.expected_revision not in revisions:
                raise LocalEndpointError("model_revision_mismatch")
        if self.config.expected_base:
            bases = {m.get("base") for m in exact if m.get("base")}
            if not bases or self.config.expected_base not in bases:
                raise LocalEndpointError("model_base_mismatch")
        return {"models": models, "selected": exact[0]}

    def decide(self, *, state: Any, questions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not questions:
            raise ValueError("questions_required")
        payload = {"model": self.config.model_id, "state": state, "questions": questions}
        start = time.perf_counter()
        result = self._request("POST", "/v1/systemone", payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        expected_response_model = self.config.expected_response_model or self.config.model_id
        if result.get("model") and result["model"] != expected_response_model:
            raise LocalEndpointError("response_model_mismatch")
        if self.config.expected_route_model or self.config.expected_route_repo:
            routing = result.get("routing")
            if not isinstance(routing, dict):
                raise LocalEndpointError("response_routing_identity_missing")
            if self.config.expected_route_model and routing.get("model") != self.config.expected_route_model:
                raise LocalEndpointError("response_route_model_mismatch")
            if self.config.expected_route_repo and routing.get("repo") != self.config.expected_route_repo:
                raise LocalEndpointError("response_route_repo_mismatch")
        answers = result.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(questions):
            raise LocalEndpointError("response_answer_coverage_mismatch")
        for question_id, answer in answers.items():
            if not isinstance(answer, dict):
                raise LocalEndpointError("response_answer_not_object")
            question = questions[question_id]
            choices = question.get("criteria") if question.get("type") == "choice" else None
            selected = answer.get("choice") or answer.get("answer")
            if isinstance(choices, dict) and selected not in choices:
                raise LocalEndpointError("response_choice_unknown")
            probabilities = answer.get("probabilities")
            if probabilities is not None:
                if not isinstance(probabilities, dict) or not probabilities:
                    raise LocalEndpointError("response_probabilities_invalid")
                values = list(probabilities.values())
                if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 1 for value in values):
                    raise LocalEndpointError("response_probabilities_invalid")
                if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-4):
                    raise LocalEndpointError("response_probabilities_not_normalized")
        result["client_elapsed_ms"] = round(elapsed_ms, 3)
        result["lane_id"] = self.config.lane_id
        result["configured_model"] = self.config.model_id
        result["verified_response_model"] = expected_response_model
        if self.config.expected_route_model:
            result["verified_route_model"] = self.config.expected_route_model
        if self.config.expected_route_repo:
            result["verified_route_repo"] = self.config.expected_route_repo
        result["confidence_definition"] = self.config.confidence_definition
        return result

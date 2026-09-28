"""Pass2 classify: label tool_calls / messages (mock by default; real when env set)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# Tools that often matter for gate / research policy
_GATE_RELEVANT = re.compile(
    r"(?i)\b(bash|shell|write|edit|delete|rm|curl|wget|fetch|http|network|pip|npm|git)\b"
)
_RESEARCHISH = re.compile(
    r"(?i)\b(websearch|webfetch|search|browser|http|curl|wikipedia|arxiv)\b"
)
_HIGH_RISK = re.compile(
    r"(?i)\b(bash|shell|write|edit|delete|rm|chmod|sudo|credential|secret|env)\b"
)


@dataclass(frozen=True)
class Classification:
    risk_class: str  # low|medium|high
    research_needed: bool
    gate_relevant: bool
    labels: tuple  # extra tags
    judge: str
    rationale: str

    def as_row_fields(self) -> Dict[str, Any]:
        return {
            "risk_class": self.risk_class,
            "research_needed": 1 if self.research_needed else 0,
            "gate_relevant": 1 if self.gate_relevant else 0,
            "labels_json": json.dumps(list(self.labels), ensure_ascii=False, sort_keys=True),
            "classify_judge": self.judge,
            "classify_rationale": self.rationale,
        }


def mock_classify_tool(tool_name: str, input_redacted: Optional[str] = None) -> Classification:
    """Deterministic offline judge — used by pytest and when no remote configured."""
    name = tool_name or ""
    blob = f"{name} {input_redacted or ''}"
    gate = bool(_GATE_RELEVANT.search(name) or _GATE_RELEVANT.search(blob))
    research = bool(_RESEARCHISH.search(name) or _RESEARCHISH.search(blob))
    if _HIGH_RISK.search(name):
        risk = "high"
    elif gate or research:
        risk = "medium"
    else:
        risk = "low"
    labels = []
    if gate:
        labels.append("gate_relevant")
    if research:
        labels.append("research_needed")
    labels.append(f"risk:{risk}")
    return Classification(
        risk_class=risk,
        research_needed=research,
        gate_relevant=gate,
        labels=tuple(sorted(set(labels))),
        judge="mock",
        rationale=f"mock heuristics on tool={name!r}",
    )


def mock_classify_message(role: Optional[str], content_redacted: Optional[str]) -> Classification:
    blob = content_redacted or ""
    research = bool(_RESEARCHISH.search(blob))
    gate = bool(_GATE_RELEVANT.search(blob))
    risk = "medium" if (research or gate) else "low"
    if role == "user" and "secret" in blob.lower():
        risk = "high"
    labels = [f"risk:{risk}", f"role:{role or 'unknown'}"]
    if research:
        labels.append("research_needed")
    if gate:
        labels.append("gate_relevant")
    return Classification(
        risk_class=risk,
        research_needed=research,
        gate_relevant=gate,
        labels=tuple(sorted(set(labels))),
        judge="mock",
        rationale=f"mock heuristics on role={role!r}",
    )


def _remote_classify(payload: Dict[str, Any]) -> Optional[Classification]:
    """
    Optional InferHub / JEV classifier HTTP JSON.

    Env:
      ACS_JEV_CLASSIFIER_URL — POST JSON, expect {risk_class, research_needed, gate_relevant, labels?, rationale?}
      ACS_JEV_CLASSIFIER_TIMEOUT — seconds (default 8)
    Fail closed → None (caller uses mock).
    """
    url = os.environ.get("ACS_JEV_CLASSIFIER_URL") or os.environ.get("ACS_CLASSIFY_URL")
    if not url:
        return None
    timeout = float(os.environ.get("ACS_JEV_CLASSIFIER_TIMEOUT") or "8")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "acs.session-ops-capture/0.1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(body, dict):
        return None
    risk = str(body.get("risk_class") or "medium")
    research = bool(body.get("research_needed"))
    gate = bool(body.get("gate_relevant"))
    labels = body.get("labels") or []
    if not isinstance(labels, list):
        labels = []
    return Classification(
        risk_class=risk,
        research_needed=research,
        gate_relevant=gate,
        labels=tuple(sorted(str(x) for x in labels)),
        judge=str(body.get("judge") or "remote"),
        rationale=str(body.get("rationale") or "remote classifier"),
    )


def classify_tool(
    tool_name: str,
    input_redacted: Optional[str] = None,
    *,
    force_mock: bool = False,
) -> Classification:
    if not force_mock:
        remote = _remote_classify(
            {"kind": "tool", "tool_name": tool_name, "input_redacted": input_redacted}
        )
        if remote is not None:
            return remote
    return mock_classify_tool(tool_name, input_redacted)


def classify_message(
    role: Optional[str],
    content_redacted: Optional[str],
    *,
    force_mock: bool = False,
) -> Classification:
    if not force_mock:
        remote = _remote_classify(
            {"kind": "message", "role": role, "content_redacted": content_redacted}
        )
        if remote is not None:
            return remote
    return mock_classify_message(role, content_redacted)

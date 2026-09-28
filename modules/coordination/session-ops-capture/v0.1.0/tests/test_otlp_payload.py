"""OTLP payload shape tests (no live network required)."""

from __future__ import annotations

from session_ops_capture.otlp import build_spans_payload


def test_otlp_payload_has_service_and_attrs() -> None:
    payload = build_spans_payload(
        tool_calls=[
            {
                "uuid": "call-1",
                "session_id": "s1",
                "tool_name": "Bash",
                "timestamp": "2026-09-27T20:00:00.000Z",
                "interaction_index": 1,
            }
        ],
        gate_events=[
            {
                "uuid": "g1",
                "session_id": "s1",
                "ts": "2026-09-27T20:00:01.000Z",
                "decision": "deny",
                "tool_name": "Bash",
                "reason_code": "mock_deny",
                "judge": "mock",
            }
        ],
        sessions=[{"session_id": "s1", "cwd": "D:\\tmp"}],
    )
    rs = payload["resourceSpans"][0]
    attrs = {a["key"]: a["value"] for a in rs["resource"]["attributes"]}
    assert attrs["service.name"]["stringValue"] == "acs.session-ops-capture"
    spans = rs["scopeSpans"][0]["spans"]
    assert len(spans) == 2
    names = {s["name"] for s in spans}
    assert "tool.Bash" in names
    assert "gate.deny" in names
    gate = next(s for s in spans if s["name"].startswith("gate."))
    gattrs = {a["key"]: a["value"] for a in gate["attributes"]}
    assert gattrs["tool.decision"]["stringValue"] == "deny"
    assert gattrs["session_id"]["stringValue"] == "s1"
    assert len(gate["traceId"]) == 32
    assert len(gate["spanId"]) == 16

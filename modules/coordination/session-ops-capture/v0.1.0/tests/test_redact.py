"""Visible red-style unit tests: redaction MUST strip secret patterns."""

from __future__ import annotations

import pytest

from session_ops_capture.redact import (
    contains_forbidden_secret_pattern,
    dumps_redacted,
    redact,
    redact_obj,
)


@pytest.mark.parametrize(
    "raw",
    [
        "api_key=sk-test-ABCDEFGHijklmnop",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaa.bbb",
        "token: ghp-abcdefghijklmnopqrstuvwxyz01",
        "export KEY=deadbeefdeadbeefdeadbeefdeadbeef",
        "sk-live-1234567890abcdef",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWX12",
    ],
)
def test_red_secrets_are_redacted(raw: str) -> None:
    """RED: if redaction fails, forbidden patterns remain — test must catch that."""
    out = redact(raw)
    assert "[REDACTED]" in out
    assert not contains_forbidden_secret_pattern(out), out
    assert "sk-test" not in out.lower() or "[REDACTED]" in out
    assert "ghp-" not in out.lower() or "[REDACTED]" in out


def test_red_nested_object_redaction() -> None:
    obj = {
        "cmd": "curl -H 'Authorization: Bearer supersecrettokenvalue'",
        "env": {"API_KEY": "sk-test-NESTEDSECRET01"},
        "hex": "0123456789abcdef0123456789abcdef",
    }
    red = redact_obj(obj)
    blob = dumps_redacted(obj)
    assert not contains_forbidden_secret_pattern(blob)
    assert "sk-test" not in blob
    assert "supersecrettokenvalue" not in blob
    assert isinstance(red["env"], dict)


def test_red_empty_passthrough() -> None:
    assert redact("") == ""
    assert redact_obj(None) is None

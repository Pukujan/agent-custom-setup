# BEHAVIOR — session-ops-capture v0.1.0

1. Pass1 ingest MUST be idempotent on UUID / tool_use id across adapters.
2. Adapters MUST emit canonical rows; new harnesses MUST NOT fork SQLite/OTLP schema.
3. Strings persisted or exported MUST be redacted.
4. Pass2 MUST run after Pass1 by default; `--no-pass2` opts out.
5. Pytest/CI MUST use mock classify + hashing embed (fail closed). Live remote
   classify/embed only when explicitly enabled and env configured.
6. Held-out FN=0 plants MUST keep `gate_relevant` true for destructive/network tools.
7. Module MUST NOT be required by hotload while status is draft/optional.

"""session-ops-capture: ACS-wide session trail (adapters → SQLite + OTLP + Pass2).

Claude Code JSONL is adapter #1; other harnesses plug into adapters/.
"""

__version__ = "0.1.0"
SERVICE_NAME = "acs.session-ops-capture"
DEFAULT_OTLP_ENDPOINT = "http://100.93.66.34:4318/v1/traces"

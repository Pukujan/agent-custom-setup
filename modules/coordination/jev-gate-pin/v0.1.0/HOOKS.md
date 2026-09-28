# Hook install — jev-gate-pin (Claude + Kilo)

## Claude Code (live wiring)

Project `.claude/settings.json` (or user `~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|WebFetch",
        "hooks": [
          {
            "type": "command",
            "command": "python \"$ACS_ROOT/modules/coordination/jev-gate-pin/v0.1.0/hooks/claude_pretooluse.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Set `ACS_ROOT` to the agent-custom-setup checkout. Pass brief/corrections via env or a small wrapper that injects pinned brief into stdin JSON.

Exit codes: Claude also honors `hookSpecificOutput.permissionDecision` (`allow`|`deny`|`ask`).

## Kilo (stub)

Discovery: `~/.kilo`, `%APPDATA%/Code/User/globalStorage/kilocode.kilo-code/`.
No stable PreToolUse API in ACS yet — use `adapters/kilo_stub.py --fixture ...` for smoke.

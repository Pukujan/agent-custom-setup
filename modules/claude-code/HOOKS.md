# Claude Code hook install (ACS three gates)

Example combined project settings (paths assume `ACS_ROOT`):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [{
          "type": "command",
          "command": "python \"$ACS_ROOT/modules/coordination/jev-ambiguity-gate/v0.1.0/hooks/claude_user_prompt.py\"",
          "timeout": 10
        }]
      }
    ],
    "SessionStart": [
      {
        "hooks": [{
          "type": "command",
          "command": "python \"$ACS_ROOT/modules/coordination/jev-research-gate/v0.1.0/hooks/claude_claim_snapshot.py\"",
          "timeout": 10
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|WebFetch",
        "hooks": [{
          "type": "command",
          "command": "python \"$ACS_ROOT/modules/coordination/jev-gate-pin/v0.1.0/hooks/claude_pretooluse.py\"",
          "timeout": 15
        }]
      }
    ]
  }
}
```

Kilo: see each module `adapters/kilo_stub.py` — discovery `~/.kilo` + `globalStorage/kilocode.kilo-code`.

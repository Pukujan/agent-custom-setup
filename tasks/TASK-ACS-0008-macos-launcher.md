# TASK-ACS-0008 — macOS single-entry InferHub Claude launcher

<!-- continuity:task {"acceptance": ["One double-clickable 'Launch Claude InferHub.command' (bash 3.2) is the only entry point; first run bootstraps uv, uv-managed Python, the litellm-ckff-ops checkout + venv with pinned litellm, and Claude Code without sudo", "InferHub key prompted once with hidden input and saved to ~/.config/inferhub/.env mode 600; never printed or logged", "LiteLLM started on 127.0.0.1:4000 only when not already healthy; 300 s health wait; fail fast on early exit", "Folder picker (~/work root + subfolders + Finder choose folder) and the Windows Top 20 model picker with the same defaults", "Seat aliases and fallback chains come from the unchanged litellm-ckff-ops scripts; claude gets the same ANTHROPIC_* env and command line as Windows", "Verified on Linux: shellcheck clean, bash -n on bash 5 and 3.2.57, tests/dry_run.sh PASS with a mock claude on a non-4000 port; Mac run still pending"], "depends_on": [], "goal": "Give Alex a one-double-click Mac launcher for Claude Code through InferHub that bootstraps itself and routes exactly like the Windows launcher.", "id": "ACS-0008", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/64", "next_action": "Alex runs the launcher once on the Mac and reports the result on #64; then owner review and merge of the PR.", "owner": "Grok Bot (executor for Alex)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "On the Mac, Claude Code through InferHub currently needs a manual install and hand-set environment variables, which is slow and can silently route requests to the wrong backend."} -->

- Status: active
- Owner / primary writer: Grok Bot (executor for Alex)
- Priority: P2
- Depends on: none in ACS. Uses Pukujan/litellm-ckff-ops `main` @ `f04adc8` (already includes litellm-ckff-ops #34 and #37)
- Leaf owning issue: [#64](https://github.com/Pukujan/agent-custom-setup/issues/64)
- Parent ancestry: [#9](https://github.com/Pukujan/agent-custom-setup/issues/9) (ACS policy + multi-setup registry + InferHub Claude module sync)
- Branch: `task/ACS-0008-macos-launcher`

## Goal

Alex double-clicks one file on the Mac. It installs whatever is missing, starts
LiteLLM, asks which folder and which models to use, and runs Claude Code through
the proxy, with the same routing as on Windows.

## Allowed files

- `modules/claude-code/inferhub-litellm-macos/v0.1.0/**`
- `registry.json` (new entry only)
- `tasks/TASK-ACS-0008-macos-launcher.md`, `checkpoints/CURRENT.md` (one Active line)

## Non-goals

- No change to the Windows module or to litellm-ckff-ops. Bringing the newer
  Desktop launcher (C:\work root, 300 s wait, fail-fast) back into ACS is a
  separate follow-up.
- No code signing or notarisation.

## Evidence

See the module's `NOTES.md` § Test evidence. In short, this was run on the
Linux box and not yet on a Mac:

- shellcheck found nothing
- `bash -n` passes on bash 5.2.37 and on bash 3.2.57
- `tests/dry_run.sh` printed PASS (mock claude, real LiteLLM 1.103.0 on 127.0.0.1:4110)
- end to end through a mock upstream, `claude-sonnet-5` reached the main seat
  and `claude-opus-5-5` reached the advisor seat
- every fail-fast path ended with a clear error

## Next atomic action

Alex runs the launcher once on the Mac and posts the result on #64. Then the
owner reviews and merges the PR.

## Checkpoint log

### 2026-10-03 — module built and verified on Linux (as-of; live issue #64 owns progression)

Completed: added the Mac launcher module (a launcher, a README, notes, the
module metadata and a dry-run test) and a registry entry for it.
Evidence: as above. Test proxies ran only on ports 4100 to 4110 of the box.
Nothing ran on port 4000 of any machine, and nothing changed on Alex's PC.
Decisions: the launcher lives in ACS because ACS is the source of truth for the
launcher. litellm-ckff-ops scripts are called rather than ported, so routing
stays identical. LiteLLM is pinned to the Windows venv versions, with uv
overrides for fastapi, starlette and sse-starlette.
Blocked/uncertain: not run on a real Mac. The Finder picker, the Command Line
Tools prompt and the Node fallback have not been run.
Next: a Mac run, then review and merge.

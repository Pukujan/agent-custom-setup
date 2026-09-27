# PROPOSALS — propose, decide, claim, PR

Mechanics for multi-agent work after this pack is hot-loaded. **PCM is continuity only** — do not store proposals, ACCEPT/REJECT rulings, or work locks in PCM checkpoints as authority. GitHub issues hold those.

Pattern references (read via GitHub; do not copy wholesale): project docs such as Jev `docs/AGENT_PROPOSALS.md`, `AUTHORITY.md`, and `HUMAN_NAMING.md`.

## Flow

```text
GitHub ticket (leaf)
    → worker posts Proposal
    → decision boss posts ACCEPT or REJECT
    → on ACCEPT: claim reserved branch (marker push)
    → implement within scope
    → small PR linking the issue
    → merge/CI per repo policy; release claim
```

Parent/child links on issues are **notes only**. There is no full DAG engine in this pack.

The **agent-less watchdog** does not ACCEPT/REJECT or appoint writers — only agents (with a valid boss lease) decide.

## 1. Propose

On the leaf issue, comment a proposal before contested implementation:

```markdown
## Proposal
**Scope:** …
**Boundary / non-goals:** …
**Dependencies:** none | …
**Done when:** …
```

Workers propose; they do not start contested work before a ruling.

## 2. Decide (decision boss only)

Boss comments clearly:

```markdown
## Decision — ACCEPT
**Primary writer:** <agent_id>
**Branch:** feat/<slug>-<issue-number>
**Conditions:** …
```

or

```markdown
## Decision — REJECT
**Reason:** …
```

Who may write ACCEPT/REJECT is the current lease holder (join-order fill + valid lease). See [ROLES.md](ROLES.md).

## 3. Claim branch + heartbeat stamps

After ACCEPT:

1. Reserve a branch named in the issue (`feat/<slug>-<n>` with issue number).
2. Push a marker commit first (empty commit is fine). If the ref already exists, stop.
3. Comment a short claim (leaf, agent, branch, state=active) and keep emitting **check-in / heartbeat stamps** while you hold work or the boss seat.
4. Then write product commits.

Agents **only emit stamps**. The agent-less watchdog reads stamps + GitHub activity; it does not replace this step.

## 4. PR and release

- Open a small PR; link with `Refs #N` for progress-only, or a closing keyword only when merge should complete the issue.
- Human-readable PR title (CGM HSW).
- Claim releases on merge or issue close, or when you explicitly mark the claim released on handoff.

## Anti-patterns

- Using PCM / continuity files as the proposal board.
- Workers ACCEPT/REJECT-ing without holding the boss lease.
- Asking an LLM or peer agent to "run the watchdog".
- Skipping the marker push and discovering collision only at PR time.
- Leading titles with `feat:` / ticket-code stacks instead of a plain sentence.
- Committing to `main`, force-pushing, or printing secrets.

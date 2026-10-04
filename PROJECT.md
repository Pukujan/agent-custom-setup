# Agent Custom Setup — Project Contract

<!-- continuity:project {"id":"agent-custom-setup","protocol_version":"0.1.0-draft","schema":"project-continuity.project.v1","title":"Agent Custom Setup"} -->

<!-- pcm:github-progression:start -->
## GitHub-owned progression

GitHub Issues are required for PCM-governed project work and own task scope, acceptance, priority, ownership, dependencies, lifecycle and durable project progression. Merged default-branch history owns accepted code and normative/domain documents; PR checks and merge records own delivery facts. Checked-in PROJECT/CURRENT/TASK/checkpoint/handoff documents are mandatory versioned projections for task state, not a parallel authority. Local files, registries, context packs and chat are ephemeral execution aids. Domain-document ownership stays with the target project.

Every issue progress update MUST link the leaf child issue that owns the work, its parent ancestry and dependencies (or explicitly none). A top-level deliverable identifies itself as the leaf and says parent: none. Create one child per independently deliverable scope, never one per comment. Record task ID, primary writer and branch on the issue before creating its repository projection. Re-read live issues and relevant source revisions before resuming; the issue verifier checks identity/status, not semantic agreement.

Authorized owner/user direction can revise intent: record it on the owning GitHub issue with a correction/supersession link before dependent work. It cannot alter observed CI/merge facts or waive required gates. Stale projections yield to their field's authority. If direction, ownership or evidence conflicts remain unresolved, pause affected work and record uncertainty; continue independent safe work. One primary writer owns each task branch/checkpoint stream. Coordinate shared-document edits through linked issues/PRs, re-read the current base and reconcile concurrent changes; never force-push or overwrite another writer. Issue prose is not an atomic lock.

Label observed results, repository/external evidence, agent reports and inference separately. Preserve contradictory evidence with source/revision and mark conclusions disputed or unknown until resolved. Append correction/supersession evidence; never rewrite checkpoint history. An upstream correction MUST identify affected descendants and assumptions on their issues; pause, re-plan and revalidate dependent work before resuming. Follow explicit parent/dependency links within the affected scope; cycles or unknown lineage block affected claims. No graph database, local canonical ledger or autonomous polling agent is required.

Before every push, synchronize relevant docs and task/checkpoint projections, CURRENT/HANDOFF when affected, and reviewed catalog/generated index. Record leaf/parent/dependency links, source issue/comment revision, as-of status, evidence, blockers and next action. Commit product/docs first; `continuity checkpoint` then commits and synchronously pushes the checkpoint with a stable request ID. After every successful push, manually publish a leaf issue receipt keyed by request ID and exact pushed SHA, linking changed docs/checkpoint, PR, tests and pending gates; add a linked parent progression update. Retry a missing receipt without another checkpoint/push; inspect for the same key before posting. --receipt-repo and --receipt-issue are opt-in and still require a proven lookup; omit them and the receipt stays manual. Automatic issue-comment synchronization is not implemented. Issue #67 remains open.

Required CI and GitHub auto-merge are mandatory. Verify protection, required reviews/checks on the exact current-base or merge-queue candidate, and auto-merge; missing, failed, skipped, stale or unverified gates fail closed: no completion or cleanup. After CI/merge, append the exact check results, PR/merge SHA and live issue status to the leaf and link the parent update; fetch and verify accepted history. Reconcile material doc/status corrections in a new synchronized increment. Receipt-only transitions need no recursive doc commit: docs retain an explicit as-of/pending state and point to the live issue. Never label local-only or merely pushed work delivered. Preserve unsafe resources and keep incomplete issues open.
<!-- pcm:github-progression:end -->

## Main goal

Run multi-agent work on one repository honestly. ACS owns **execution coordination**:
turning logged tickets into workable tasks, decomposing them, and keeping several
agents on one repo from colliding — join-order roles, a boss lease with FIFO
failover, a GitHub-canonical claim queue, an agent-less watchdog, and proposals.
The product it ships is the **multi-agent hotload pack**; ACS pins PCM and CGM as
external authorities and vendors neither.

## Why

Agents are cheap to run and expensive to coordinate. Without a shared, versioned
install surface, two agents on one repository duplicate work, act on stale state,
or disagree with no tie-breaker. ACS answers the *coordination* half of that
problem and nothing else — it does not log tickets, write prose, own versions, or
make decisions on the agents' behalf.

## Scope

- The multi-agent hotload pack: roles, boss lease + failover, claim queue,
  agent-less watchdog, proposals, and the install/verify surface
  (`hotload_check.py`, `check_pins.py`, the pinned FULL PCM + FULL CGM stack).
- Execution coordination: making tickets workable, breaking them down, and
  sequencing the agents that run them.
- A future **DAG++** execution layer is ACS-owned.

## Non-goals

- **Not ticket logging.** The issue form, filer stamp, triage and prioritization
  belong to OIO (Observational Issue Ops). ACS *runs* tickets; it does not file them.
- **Not decision-making.** Adjudication / tie-breaking between agents is JEV's
  intended job; JEV is not strong enough for it yet and is parked (see `jev-dump`).
- **Not continuity, narrative, or versions.** Those belong to PCM, CGM, and the
  release train respectively. ACS pins them; it does not replace or vendor them.
- **Not a runtime-safety or benchmarking home.** The JEV gates, `jev-omp`, and
  `jev-benchmark` moved out to `jev-dump`; the `[CC]` launcher moved to
  `claude-code-launcher`. ACS no longer carries either.

## Definition of success

An agent told to load the hot-loader into a working repo finishes with the FULL
PCM + FULL CGM stack pinned and validated, the coordination runtime wired, and
`hotload_check.py` green — and the coordination rules (roles, lease, claim queue,
watchdog) hold under concurrent agents without a human arbitrating every step.
Drift in the advertised pins fails closed.

## Layer ownership (the stack, one line each)

| Layer | Repo | Owns |
| --- | --- | --- |
| Ticket logging | OIO | Writing issue tickets **only** — the form, the filer stamp, the triage, and how to handle/prioritize them. **Not coordination.** |
| Execution coordination | **ACS (this repo)** | **Running** the tickets: making them workable, breaking them down, coordinating the agents. The multi-agent hotload pack. Future DAG++ layer. |
| Continuity | PCM | Tasks, checkpoints, push receipts, PR gates, the `continuity` CLI. |
| Narrative | CGM | Writing routing, prose, naming, visual direction, image gen, HTML demos. |
| Versions | train | The certified version set. |
| Decision-making | JEV | Aspirational arbiter / tie-breaker — **parked** in `jev-dump`; not strong enough yet. |

This table supersedes the earlier filed proposals that placed coordination in OIO
(ACS #52) or kept JEV parked inside ACS (#44, #63).

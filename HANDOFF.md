# Current Handoff

Start from repository state, not prior chat history.

## Read order

1. `PROJECT.md`
2. `AGENTS.md` when present
3. `checkpoints/CURRENT.md`
4. the active task named by CURRENT
5. the minimum relevant specification/design document

Before editing a GitHub task, run `continuity issue verify <TASK-ID>` and confirm the live issue is open and matches the task.

## Authority

GitHub Issues are authoritative for task scope, priority, ownership, dependencies, acceptance, and lifecycle; the linked task file is a compact working cache. Merged default-branch history is authoritative for accepted code. PR checks and merge evidence are authoritative for delivery. Chat and context packs are derived. Before resuming, verify the linked issue and read current GitHub status.

When a GitHub issue reference appears in a pull-request description or commit message, use a supported issue-closing keyword only when merging should complete that issue. GitHub treats `close`, `closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves`, and `resolved` followed by an issue reference as a close directive; negation does not cancel it. For progress-only work, link with `Refs #<number>` or the GitHub sidebar. After each merge, verify the live issue state before changing task status. See [GitHub's issue-linking rules](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue).

<!-- pcm:github-progression:start -->
## GitHub-owned progression

GitHub Issues are required for PCM-governed project work and own task scope, acceptance, priority, ownership, dependencies, lifecycle and durable project progression. Merged default-branch history owns accepted code and normative/domain documents; PR checks and merge records own delivery facts. Checked-in PROJECT/CURRENT/TASK/checkpoint/handoff documents are mandatory versioned projections for task state, not a parallel authority. Local files, registries, context packs and chat are ephemeral execution aids. Domain-document ownership stays with the target project.

Every issue progress update MUST link the leaf child issue that owns the work, its parent ancestry and dependencies (or explicitly none). A top-level deliverable identifies itself as the leaf and says parent: none. Create one child per independently deliverable scope, never one per comment. Record task ID, primary writer and branch on the issue before creating its repository projection. Re-read live issues and relevant source revisions before resuming; the issue verifier checks identity/status, not semantic agreement.

Authorized owner/user direction can revise intent: record it on the owning GitHub issue with a correction/supersession link before dependent work. It cannot alter observed CI/merge facts or waive required gates. Stale projections yield to their field's authority. If direction, ownership or evidence conflicts remain unresolved, pause affected work and record uncertainty; continue independent safe work. One primary writer owns each task branch/checkpoint stream. Coordinate shared-document edits through linked issues/PRs, re-read the current base and reconcile concurrent changes; never force-push or overwrite another writer. Issue prose is not an atomic lock.

Label observed results, repository/external evidence, agent reports and inference separately. Preserve contradictory evidence with source/revision and mark conclusions disputed or unknown until resolved. Append correction/supersession evidence; never rewrite checkpoint history. An upstream correction MUST identify affected descendants and assumptions on their issues; pause, re-plan and revalidate dependent work before resuming. Follow explicit parent/dependency links within the affected scope; cycles or unknown lineage block affected claims. No graph database, local canonical ledger or autonomous polling agent is required.

Before every push, synchronize relevant docs and task/checkpoint projections, CURRENT/HANDOFF when affected, and reviewed catalog/generated index. Record leaf/parent/dependency links, source issue/comment revision, as-of status, evidence, blockers and next action. Commit product/docs first; `continuity checkpoint` then commits and synchronously pushes the checkpoint with a stable request ID. After every successful push, manually publish a leaf issue receipt keyed by request ID and exact pushed SHA, linking changed docs/checkpoint, PR, tests and pending gates; add a linked parent progression update. Retry a missing receipt without another checkpoint/push; inspect for the same key before posting. Automatic issue-comment synchronization is not implemented.

Required CI and GitHub auto-merge are mandatory. Verify protection, required reviews/checks on the exact current-base or merge-queue candidate, and auto-merge; missing, failed, skipped, stale or unverified gates fail closed: no completion or cleanup. After CI/merge, append the exact check results, PR/merge SHA and live issue status to the leaf and link the parent update; fetch and verify accepted history. Reconcile material doc/status corrections in a new synchronized increment. Receipt-only transitions need no recursive doc commit: docs retain an explicit as-of/pending state and point to the live issue. Never label local-only or merely pushed work delivered. Preserve unsafe resources and keep incomplete issues open.
<!-- pcm:github-progression:end -->

## Workspace mode: single checkout

Use the main checkout for sequential work. Do not create clones or linked worktrees. This is the strictest and simplest option when parallel isolation is not needed.

## Finding earlier project documents

When `.continuity/documents.json` is present, it is the machine-readable inventory and `docs/CONTINUITY_INDEX.md` is its generated human view. Every fresh session or task takeover/resumption must consult the inventory before choosing its next action, not only before writing a document: run `git fetch origin`, then use `continuity docs find "<issue title and task-objective terms>" --task <TASK-ID>` and read matching records and their declared neighbors. The search is deterministic metadata search, not semantic whole-repository search. `continuity validate` checks the generated view; use `continuity docs render` to refresh its freshness labels after source edits. A `NEEDS_REVIEW` result preserves historical evidence but says not to rely on it without checking the current file.

## Continuity records

<!-- pcm:policy {"id":"continuity-records","policy_version":"1.2.0","protocol_version":"0.1.0-draft"} -->

Write continuity issues, updates, pull requests, and project-state documents so a fresh reader can understand the problem, human outcome, scope, evidence, and next action. Cite external claims and link repository claims to a revision or CI result. Include reproduction detail only when needed to verify the claim. Keep PR openings skimmable; link long logs. Do not claim automatic tracker synchronization or chat capture unless implemented and tested.

## Degraded continuity

Execution safety and existing authorization outrank continuity bookkeeping. If a canonical continuity file is temporarily unavailable, do not stop safe work, repair storage just to force a checkpoint, or ask again for an already-authorized host/worktree. Use an authorized alternate checkout and run `continuity checkpoint <TASK-ID> --root <canonical-root> --recovery-root <alternate-root> ...` to write a JSON recovery receipt under `.continuity/recovery/`; do not create an ad-hoc Markdown checkpoint or replace the alternate task file. Reconcile it into the canonical task with `continuity recovery reconcile --root <canonical-root> --file <receipt>` when writable. The repository/task lineage is authoritative; a physical path is not.

Normal checkpointing is a delivery operation, not a local note: commit the product change first, then run `continuity checkpoint`. The command prints a `REQUEST_ID`, commits the canonical checkpoint and synchronously pushes the task branch to `origin`; if interrupted, rerun with the same `--request-id` to avoid a duplicate (changed payload with the same ID is rejected). Open or update a PR after pushing. GitHub CI and auto-merge then run asynchronously and wait for required reviews/checks and any merge queue. Confirm the merge before marking the task complete or removing its worktree.

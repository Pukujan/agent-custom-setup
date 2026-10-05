# SPEC — the hotload install contract (normative)

This is the contract the multi-agent hotloader must satisfy. It is written so a
fresh agent — on Windows, macOS, or Linux — can install the pack into a working
repo that **already contains content**, and either complete the install or be
told exactly why it could not, without any file being damaged on the way.

[HOTLOAD.md](HOTLOAD.md) is the load order. [BEHAVIOR.md](BEHAVIOR.md) is the
operating rules. This file is the **install contract**: what "installed" means,
what happens at every path that already exists, and what must be true when the
command exits.

## 1. Version source — the release train, not a copied pin

The pack does **not** hand-hold component versions. The certified version set
lives in `agent-stack-train`'s `stack-releases.json`, and it is the single
source of truth for what "current" means.

| Record | Owner | What it is | What it is NOT |
| --- | --- | --- | --- |
| `stack-releases.json` | train | The certified version set (one entry per component). | Not an adopter's pin. |
| `stack-mesh.json` | each stack repo | That repo's **requirement**, written from the train by the train's `mesh.py` and enforced by the train's `require-mesh.yml` CI. | Not hand-edited; an older requirement fails CI. |
| `pins.json` | ACS (this pack) | **Module shape only** — the CGM module list/count and the ACS module id/version. | Not a version pin. Component commits are not copied here. |
| `stack-manifest.json` | the adopter | The adopter's own pins. **Empty entries follow the train.** | Not a frozen copy of install-day versions. |
| `.coord/hotload.lock.json` | the adopter | A **historical** record of what was installed, and when. | Not a forward pin — it must never hold an adopter back. |

**Binding:**

- Version requirements live in `stack-mesh.json`, generated from the train by
  the train's own `mesh.py`. This pack MUST NOT carry a second, hand-maintained
  copy of component commits — a copied pin is exactly the drift the train exists
  to remove.
- The installer MUST write the adopter's `stack-manifest.json` with **empty
  pins** (follow the train) and MUST NOT write install-day versions into it.
- `hotload_check` MUST NOT validate the adopter's checkouts against the frozen
  lock. The lock is evidence of the install, not a ceiling on it.

Rationale: a copied pin is how the 2026-10-01 snapshot stayed on PCM 0.6.0 after
0.7.0 had shipped. The train exists so that stops happening.

## 2. What "installed" means (done-when)

Install is complete only when **all** of the following hold, as **full stacks**:

1. **FULL PCM** at the train's certified revision — continuity/checkpoints **and**
   GitHub-owned progression (PR-only, required CI gates, protection/auto-merge
   preference, fail-closed gates, leaf/parent receipts). Not the proposal layer.
2. **FULL CGM** at the train's certified revision — all eight modules including
   `human-output-naming`, plus the `human_output_contract`.
3. **The coordination runtime** — join-order roles, boss lease (minutes),
   GitHub-canonical FIFO claim queue, agent-less watchdog, proposals → claim → PR.
4. **OIO** — the observational issue-log surface (ontology, issue form, triage
   workflow, `AGENTS.md` guidance block) installed into the adopter.
5. The adopter follows the train via `stack-manifest.json` and a
   `check_manifest.py` CI step.
6. `hotload_check` reports `OK`, and the lock records state `READY`.

Missing any item, or substituting a slim subset, is an **incomplete install**.
An incomplete install MUST be reported as incomplete — never as success.

## 3. The install state machine

The installer is a conductor, not a copier. It computes a **plan** for the whole
repo, evaluates every gate, and writes only if nothing is unresolved.

States, read from the adopter's own records:

| State | Meaning |
| --- | --- |
| `ABSENT` | No coordination surface and no component records. A first install. (The CGM `.content-system/` adapter is a precondition the adopter already carries, not a component this installer writes, so it does not make a repo `PARTIAL`.) |
| `PARTIAL` | Some records present but not all — e.g. the coordination surface is written but OIO is not installed. Resumable. |
| `READY` | The coordination surface, the adopter `stack-manifest.json`, and the OIO manifest are all present. A rerun is a no-op. |
| `DRIFTED` | Installed, but behind the train. Report; do not silently move. |
| `CONFLICTED` | A target path exists with foreign content. The plan refuses: zero writes, non-zero exit. Reported by the plan, not persisted in the lock. |
| `RECOVERING` | An install journal is present. Recover before anything else. |

Transitions:

```
ABSENT ──plan ok──▶ READY
ABSENT ──conflict──▶ CONFLICTED         (no writes)
PARTIAL ─plan ok──▶ READY
READY ──rerun─────▶ READY               (no-op, idempotent)
READY ──train moves─▶ DRIFTED ──apply──▶ READY
any ──journal─────▶ RECOVERING ──recover──▶ prior state
```

**Order of gates, all before the first byte is written:**

1. **Target** — the target is an existing git repo, is not the source repo, and
   the platform supports the filesystem operations the component needs.
2. **State** — read the adopter's manifests and journals; resolve `RECOVERING`.
3. **Plan** — ask each component for a dry-run plan; aggregate.
4. **Conflict gate** — classify every target path (§4). Any unresolved path ⇒
   **zero writes**, print the report, exit non-zero.
5. **Apply** — journal → write → verify → rollback on any failure.
6. **Record** — write the lock (state, versions, per-artifact provenance).

## 4. Per-artifact gate — what happens when a path already exists

Never clobber. Every target path is classified before any write. There are two
layers, because two kinds of file exist.

**Layer A — files this installer owns** (`.coord/assignment.json`,
`.coord/hotload.lock.json`, `stack-manifest.json`). `acs_install.py`'s
`gate_plan` classifies each:

| Existing path | Action |
| --- | --- |
| absent | **create** |
| ours — under `.coord/`, or carrying our `schema_version` | **keep** — never clobber; `--force` regenerates |
| foreign, byte-identical to what we would write | **adopt** — treat as ours |
| foreign, different | **refuse** — zero writes, exit non-zero, name the path |
| symlink or not a regular file | **refuse** (fail closed) |

`assignment.json` is *designed to be edited*: the README tells the operator to
edit the `agents` list and `check_in` to match their seats and issue. So an
edited `.coord/` file is **kept** and the install still succeeds — it is not a
conflict, and the rerun stays idempotent. `--force` is the explicit operator
choice to regenerate it.

**Layer B — shared, human-owned files** (`AGENTS.md`, `README.md`, `PROJECT.md`,
`HANDOFF.md`, `.github/workflows/*`). No component owns these wholesale; each
owns a delimited region (§5). The region merge — insert-or-update inside the
start/end markers, refuse on a hand-edited region (hash mismatch) — is performed
by the **component's own installer** (OIO does this for `AGENTS.md`), not by
`gate_plan`. ACS invokes that installer and reports its refusal; it does not
re-implement the merge.

The default on any ambiguity is to stop. `--adopt` and quarantine to
`<path>.acs-new` are **not** implemented in v1; refuse-and-report is the
default, and `--adopt` remains an open question (§9).

`.coord/` is a reserved directory: if it already holds files that are not ours,
that is a conflict, and the installer refuses rather than treating the directory
as a free space to populate.

## 5. Shared, human-owned files

Some files are never wholesale-owned by any component: `AGENTS.md`, `README.md`,
`PROJECT.md`, `HANDOFF.md`, and `.github/workflows/*`. Each component owns a
**delimited region** inside them, marked by a start/end comment pair (OIO already
does this for `AGENTS.md` with `<!-- oio:issue-log-guidance:start/end -->`).

- Install **inserts or updates the region**; everything outside it is untouched.
- An edited region is detected by hash and **refused**, not overwritten.
- Component-owned directories (`.oio/`, `.coord/`, `.content-system/`,
  `.continuity/`) are owned, but only files the component wrote are overwritten,
  tracked by hash.

## 6. Platform matrix

Every installer must run on Windows, macOS, and Linux.

| Component | Windows | macOS | Linux |
| --- | --- | --- | --- |
| ACS hotloader | ✅ stdlib | ✅ | ✅ |
| PCM CLI | ✅ | ✅ | ✅ |
| CGM validator | ✅ | ✅ | ✅ |
| OIO installer | ✅ (port required) | ✅ | ✅ |

The OIO installer's security control — refusing symlink/reparse-point
redirection of a managed write outside the target — MUST be preserved on every
platform. On POSIX it uses descriptor-relative `O_NOFOLLOW` operations; on
Windows it uses `os.lstat` reparse-point checks and/or `CreateFileW` with
`FILE_FLAG_OPEN_REPARSE_POINT`. Where a platform genuinely cannot support the
control, the component fails closed and the install is `PARTIAL` — never faked.

Linux validation runs in a container (`python:3.12` + `jsonschema`) so the POSIX
path is exercised without a Linux host.

## 7. Failure behavior

- **Fail closed.** Any unmet gate ⇒ zero writes and a non-zero exit.
- **No fake success.** A partial install reports exactly which component is
  missing, why, and the one command that finishes it.
- **Atomic writes.** Every file is written via a temp file and replaced.
- **Recoverable.** An interrupted install is restored from its journal on the
  next run.
- **No network at install.** The installer never clones, fetches, or vendors
  PCM/CGM/OIO source. Checkouts are brought at the pinned revisions.

## 8. Test plan (the taxonomy this contract is proven against)

Each claim above is backed by more than one kind of test:

| Kind | What it proves | Where |
| --- | --- | --- |
| **PDD** (acceptance) | A fresh adopter reaches `READY`; a conflicted repo is refused with a clear report. | `tests/test_install_acceptance.py` |
| **SDD** (spec/semantics) | The state machine's states and transitions match this document. | `tests/test_install_states.py` |
| **TDD** (unit) | Each gate (§4) classifies each path kind correctly. | `tests/test_install_gates.py` |
| **Metamorphic** | Reordering components, or rerunning install, does not change the final tree; an added foreign file cannot be overwritten. | `tests/test_install_metamorphic.py` |
| **Differential** | The adopter's `stack-manifest.json` agrees with the **live** train (`check_manifest.py`); the pack's `stack-mesh.json` sits at the certified commits (`mesh.py --check`). | `tests/test_install_manifest.py` (offline shape) + the train's `check-adopter.yml` / `require-mesh.yml` (live) |
| **Formal** | The state machine's safety (no write outside target, no clobber of foreign/edited content, idempotence, fail-closed) is model-checked. | `formal/install.tla` + `formal/README.md` |
| **Hidden holdout** | A blind agent, given the pack cold, installs it correctly into a repo that already has content — or correctly refuses. | `holdouts/HLD-0001-blind-rubric.md` (rubric) + `holdouts/HLD-0001-verify.sh` (seeded check of the discriminating criteria) |

## 9. Open questions for the owner

- Does `--adopt` belong in v1, or is refuse-plus-quarantine enough?
- Should `DRIFTED` auto-apply on a scheduled run, or stay report-only until a
  human runs the update?

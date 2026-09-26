# ACS-0003 reader-task evaluation (spec-driven, provenance)

Owner direction 2026-09-25: use researched specs with provenance and
property/metamorphic/benchmark tests, not guessing; use omp CLI sessions for
differential and iterative tests. This harness implements that against the pinned
CGM helper `content-generation-modules` @
`f85e88bc00362c53061d95ac7811bd9c6ada8e32`, docs/README_QUALITY_TDD.md and
docs/HOLDOUT_EVALUATION.md.

## Design

- **Reader tasks (T1–T5)** from README_QUALITY_TDD.md "Product acceptance tasks":
  explain who/situation/difficulty; offer+mechanism without internal file names;
  shipped-vs-pending-vs-planned; one claim's evidence and its non-proof; smallest
  next action + reproduce path.
- **Arms**: each answer comes from a fresh headless `omp -p` session (model
  `haiku`), shown ONLY the variant README + one task prompt (inline; `--no-tools`
  prevents file access), required to emit JSON. No saved session.
- **Grading is deterministic**: per-field any-of anchors + forbidden-token lists
  in `reader_tasks.json`. No LLM judge, no word count (per the TDD doc's own
  warning).
- **Variants** built deterministically by `build_variants.py` (asserts fail loudly
  if a transform matches nothing or changes unintended content): `current`,
  `stub` (differential baseline = the `1c44c8d` placeholder README), `reordered`
  (M-01), `bold_stripped` (M-09), `claim_removed` (M-04: removes every carrier of
  the pending-merge module claim; asserts no residual citation, no collateral).

## Expectations (frozen per revision, applied by `score.py`)

- `current`: T1–T5 pass on every arm.
- `reordered`, `bold_stripped`: per-task majority pass-set (≥3 arms) equals
  `current` (invariance).
- `claim_removed`: T3 fails on every arm — sole evidence for the pending-merge
  claim removed → status unstatable (removal must weaken).
- `stub`: differential observation only — current must not score below the stub.

## Final verdict (suite 4, key v3, 2026-09-26T02:08–02:46Z, 12 arms / 60 sessions)

```text
current          2 arms PASS
stub             obs: current=5.0/5 (2 arms) vs stub=2.0/5 (2 arms)   [no regression]
reordered        PASS majority=[T1..T5] (3 arms)     [M-01 invariance]
bold_stripped    PASS majority=[T1..T5] (3 arms)     [M-09 invariance]
claim_removed    PASS T3-fail on all 2 arms          [M-04 evidence removal]
HOLDOUT: not_run
SUITE: PASS
```

Reproduce with `python3 evals/score.py` over the committed records. Raw per-arm
records (answers, reasons, pass flags): `evals/results/run_*.json`; earlier-key
runs archived in `v1-prekey/` and `v2-prekey3/` and a single hardened stub smoke
in `smoke/` (subdirectories are excluded from `score.py`'s glob — pool hygiene so
future suites can't silently mix cohorts; archives kept for audit). The README
iteration this suite motivated is the "Status at a glance" line
(order-independent shipped/pending/planned summary), driven by v1/v2 invariance
failures localized to status-mapping fragility.

## Key revision history (fully disclosed)

- **v1** (00:00Z): initial key; 50-arm suite 01:00–01:20Z → two invariance FAILs;
  stored answers showed anchor gaps ("multi-module adoption"; "reproducibility
  beyond…"), not README defects. The full v1 suite survives at
  `evals/results/v1-prekey/` (an earlier draft wrongly said v1 was deleted — only
  the first 10-arm smoke file was removed; fixed here). The pre-status-line README
  v1 graded is uncommitted, so v1→v2 deltas are re-readable from JSON, not
  re-buildable from git.
- **v2** (01:25Z): synonym anchors; 50-arm suite → current/stub/claim_removed/
  reordered pass; `bold_stripped` flaked 1 arm on paraphrase (T1 "lost between
  sessions", T2 "survive/reviewed").
- **v3** (02:00Z): monotone-anchor policy (gain-only, never remove/tighten, so no
  prior pass flips) + majority over ≥3 arms; suite 4 above.
  **Post-suite admission:** v3's note claimed no anchors were copied verbatim from
  failing answers; that is not fully true — T1 gained `"lost between"` /
  `"cannot be reviewed"` and T2 `"survive"`, copied from bold_stripped run2
  wording (general forms `lost`/`review` would have sufficed). Anchor lists were
  unchanged during suite 4, so all suite-4 verdicts stand as scored.

## Limitations (not overclaimed)

- **Isolation / cohort — settled by evidence, not assumption.** An interim
  disclosure here claimed the suite-4 `stub` may have run under hardened flags
  (mid-loop edit). Verification refutes that and confirms uniform conditions:
  (1) `run_arms.py` mtime = 22:13Z (pre-edit original) vs `stub` launch
  02:46:17Z — the file on disk at launch was the original code; (2) zero advisor
  log lines in the arms' window and zero `__advisor.*.jsonl` artifacts under this
  repo's session dirs (they exist only in an unrelated old /tmp session) — `-p`
  print mode never engaged the ambient `advisor.enabled: true`; (3) per-arm
  duration tracks input size (stub ~10 s/arm, others ~31–90 s/arm), not an
  isolation change. All five suite-4 variants therefore ran the same
  original-condition runner: the differential and invariance comparisons are
  like-for-like. External advisor state is not directly observable, so (2) is
  evidence, not a proof-by-observation — labeled *inferred*.
- The hardened runner (v2: committed `evals/omp-arms-overlay.yml` with hard-fail,
  `--no-rules --no-extensions --no-skills`, sha256, full answers) applies to
  FUTURE suites. Its records state `advisor_overlay_passed: true` and
  `advisor_effect: "unverified"` — the overlay is *passed*, and the speed/log
  evidence is consistent with advisor-off, but omp does not report config-merge
  results, so the machine-readable field never claims more than it observes.
- Suite-4 records (`arm-run.v1`) store 200-char-truncated answers and no sha256,
  so re-gradation under future keys is approximate; v2 records store full answers
  for exactly this reason.
- The **reader is a model arm**, not a human; per README_QUALITY_TDD.md this is a
  deterministic proxy, and writer/reader share a model family → **not** the
  independent review the release gate requires; a human pass remains open.
- **Holdout = `not_run`:** no sealed target/key/independent evaluator exists, and
  this key lives inside the repo a future arm could read — so no "hidden" claim.

## Reproduce

```bash
python3 evals/build_variants.py
for v in current reordered bold_stripped claim_removed stub; do
  python3 evals/run_arms.py --variant "$v"   # counts from key runs_per_variant
done
python3 evals/score.py
```

`continuity validate` VALID and the pinned CGM adapter validator exit 0 remain the
deterministic contract gates; this directory is the reader/property layer on top.

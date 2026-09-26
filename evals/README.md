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

## Final verdict (suite 4, key v3, 2026-09-26T02:08–02:46Z, 13 arms / 65 sessions)

```text
current          2 arms PASS
stub             obs: current=5.0/5 (2 arms) vs stub=2.0/5 (2 arms)   [no regression]
reordered        PASS majority=[T1..T5] (3 arms)     [M-01 invariance]
bold_stripped    PASS majority=[T1..T5] (3 arms)     [M-09 invariance]
claim_removed    PASS T3-fail on all 2 arms          [M-04 evidence removal]
HOLDOUT: not_run
SUITE: PASS
```

Raw per-arm records (answers, reasons, pass flags): `evals/results/run_*.json`;
earlier-key runs archived in `v1-prekey/` and `v2-prekey3/` (excluded from the
pooled verdict above, retained for audit). The README iteration this suite
motivated is the "Status at a glance" line (order-independent shipped/pending/
planned summary), driven by v1/v2 invariance failures localized to
status-mapping fragility; the residual v3 anchor-gap classification is below.

## Key revision history (fully disclosed)

- **v1** (00:00Z): initial key; 50-arm suite 01:00–01:20Z → two invariance FAILs;
  stored answers showed anchor gaps ("multi-module adoption"; "reproducibility
  beyond…"), not README defects. The full v1 suite survives at
  `evals/results/v1-prekey/` (an earlier draft of this section wrongly said v1 was
  deleted — only the first 10-arm smoke file was removed). The pre-status-line
  README v1 graded is uncommitted, so v1→v2 deltas are re-readable from JSON, not
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

- **Isolation gap, disclosed:** all reported records (schemas `arm-run.v1`) ran
  with cwd=repo, default rules discovery, and ambient advisor config (no
  `--no-rules/--no-extensions/--no-skills`, advisor not overlay-disabled).
  Bounding evidence: identical-environment `stub` scored 2.0/5 vs `current` 5/5,
  and `claim_removed` degraded only T3 — contamination would not reproduce that
  spread. The runner is now hardened (v2: isolation flags, advisor-off overlay,
  sha256, full stored answers) for future runs; v1 answers are truncated to 200
  chars, so future keys can't re-grade exactly — next iteration re-runs clean.
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

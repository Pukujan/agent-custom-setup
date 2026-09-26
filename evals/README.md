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

Reproduce with `python3 evals/score.py --dir evals/results` (the committed
suite-4 cohort). Raw per-arm records: `evals/results/run_*.json`; earlier-key
runs archived in `v1-prekey/`, `v2-prekey3/`, and a single hardened-runner stub
smoke in `smoke/` (subdirectories are excluded from flat pooling; see
Cohorts). The README iteration this suite motivated is the "Status at a glance"
line (order-independent shipped/pending/planned summary), driven by v1/v2
invariance failures localized to status-mapping fragility.

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

## Cohorts and isolation (bounded, not "verified")

A mid-suite edit (~02:34Z) added isolation flags to `run_arms.py` while keeping
the v1 record shape; the full v2 record rewrite (sha256, `arm_flags`,
`answer_full`) landed after suite 4. What the records prove:

- `stub` launched 02:46:17Z wrote a **v1/no-flags** record, and the hardened
  smoke wrote v2 at 03:29Z ⇒ the v2 rewrite falls in **(02:46Z, 03:29Z]**, but
  the flag-only intermediate also wrote v1 — so **whether suite-4's `stub` arms
  ran with isolation flags is indeterminate from the records**. The other four
  variants launched before ~02:31Z and are firmly original-condition.
- Two earlier "verification" legs are **retracted**: (1) `run_arms.py` mtime —
  `git checkout` during merge work rewrites mtimes (observed 03:45:40Z =
  checkout, not authoring); (2) "no `__advisor.*.jsonl` under this repo's
  session dirs" — false: such files exist there (they belong to the parent
  interactive session); arms used `--no-session` and never write session dirs,
  so the absence/presence channel is uninformative either way.
- Mitigation: the 03:29Z **hardened** single-arm stub run (`smoke/`, schema v2,
  flags+sha256 recorded) independently fails 4/5 tasks (T2 only pass) — the
  stub-inferiority direction of the differential does not depend on suite-4's
  cohort question.
- Weak supporting observation: per-arm duration tracks input size (stub 4.5 KB
  ≈10 s/arm vs current 13.7 KB ≈31 s/arm), consistent with — but not proof of —
  identical runner code.
- Conclusion, labeled: the M-01/M-04/M-09 verdicts are within one cohort
  (original conditions, current included) and stand. The current-vs-stub
  differential is either same-cohort (if stub ran original) or cross-cohort with
  the smoke as independent confirmation; either way the direction holds, and no
  uniformity claim stronger than that is made.
- Whether `-p` engages the ambient advisor cannot be observed externally;
  records state `advisor_overlay_passed` + `advisor_effect: "unverified"`
  (intent vs observation). The already-committed v2 smoke record predates the
  field rename and carries the original boolean `advisor_enabled_during_run`;
  future records use **schema `arm-run.v2.1`**. Suite-5 (fully hardened
  current+stub, ~4 min) is recorded as a next action, not run (owner: stop).

## Limitations (not overclaimed)

- The **reader is a model arm**, not a human; per README_QUALITY_TDD.md this is a
  deterministic proxy, and writer/reader share a model family → **not** the
  independent review the release gate requires; a human pass remains open.
- Suite-4 records (`arm-run.v1`) store 200-char-truncated answers and no sha256,
  so re-gradation under future keys is approximate; v2.1 records store full
  answers for exactly this reason.
- **Holdout = `not_run`:** no sealed target/key/independent evaluator exists, and
  this key lives inside the repo a future arm could read — so no "hidden" claim.

## Reproduce

```bash
python3 evals/build_variants.py
# fresh cohort into its own directory so score.py never pools two runners:
python3 evals/run_arms.py --variant current --out evals/results/suite5
python3 evals/score.py --dir evals/results/suite5          # suite-5 verdict
python3 evals/score.py --dir evals/results                 # committed suite 4
```

`continuity validate` VALID and the pinned CGM adapter validator exit 0 remain the
deterministic contract gates; this directory is the reader/property layer on top.

# Formal model — the install state machine

`install.tla` model-checks the safety of the hotload install rule described in
[`../SPEC.md`](../SPEC.md) sections 3-4: classify every target artifact, and
write only when nothing is unresolved.

## What it proves

| Invariant | Meaning |
| --- | --- |
| `TypeOK` | The model is well-formed (kinds are valid, `written` is a set of artifacts). |
| `NoClobber` | An artifact that must be refused (`foreign_different`, `not_regular`) is never written. |
| `FailClosed` | If any artifact is unresolved, **no** artifact is written. |
| `InTarget` | Writes only ever touch the declared artifact set. |
| `Idempotent` | A clean state has written only what a clean plan writes, so re-applying adds nothing. |

The kinds are exactly SPEC.md section 4 Layer A: `absent` (create), `ours_*`
(keep; `--force` regenerates), `foreign_identical` (adopt), `foreign_different`
(refuse), `not_regular` (refuse — symlink or directory). An **edited** owned
file (`ours_edited`) is *kept*, not refused — the assignment is designed to be
edited — so it is in the writable set, never the refused set.

The model is deliberately small. It abstracts a target path to its
classification and models only the two actions the installer takes — apply a
clean plan, or refuse — because those are the properties the contract rests on.
It is not a model of the filesystem.

## Running it

TLC ships in `tla2tools.jar` (requires Java 11+):

```bash
java -cp tla2tools.jar tlc2.TLC -config install.cfg install.tla
```

Expected output ends with:

```
Model checking completed. No error has been found.
```

`Artifacts = {a1, a2, a3}` in `install.cfg` is enough to cover every
classification: with three artifacts and six kinds, TLC explores the
clean/unclean split and the write/no-write decision exhaustively.

`Mode` selects what a clean apply writes: `"normal"` creates the absent
artifacts; `"force"` additionally regenerates the ones we own. The config
checks `"force"` (the larger write set); flip it to `"normal"` and re-run — both
must hold.

## Scope and limits

- The model covers the **decision** (write vs. refuse), not the byte-level
  merge. The delimited-region merge (SPEC.md section 5, Layer B) and the hash
  guard are covered by the metamorphic and gate tests, not here.
- It proves the rule is safe **as specified**. If the implementation writes
  before it classifies, the model does not catch that — the acceptance and
  gate tests do.

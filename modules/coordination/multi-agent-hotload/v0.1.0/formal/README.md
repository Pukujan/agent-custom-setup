# Formal models — install and seat

Two TLA+ models are checked by TLC here:

- **`install.tla`** — the hotload install rule ([`../SPEC.md`](../SPEC.md)
  sections 3-4): classify every target artifact, write only when nothing is
  unresolved.
- **`seat.tla`** — the seat protocol ([`../ROLES.md`](../ROLES.md); executed by
  [`../scripts/seat_protocol.py`](../scripts/seat_protocol.py)): a boss lease, a
  FIFO claim queue, an agent-less watchdog, zombie rejection, and append-only
  as-of history.

Both are deliberately small. Each abstracts away the bytes on disk — the
filesystem for install, the claim record for the seat — and model-checks only
the safety properties the contract rests on.

## Install state machine (`install.tla`)

`install.tla` model-checks the safety of the hotload install rule described in
[`../SPEC.md`](../SPEC.md) sections 3-4: classify every target artifact, and
write only when nothing is unresolved.

### What it proves

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

### Running it

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

## Seat protocol (`seat.tla`)

`seat.tla` model-checks the safety of the seat state machine that
[`../scripts/seat_protocol.py`](../scripts/seat_protocol.py) executes and
[`../ROLES.md`](../ROLES.md) specifies.

### What it proves

| Invariant | Meaning |
| --- | --- |
| `TypeOK` | The model is well-formed (seat, status, check-ins, queue, history, and clock stay in their domains). |
| `AtMostOneBoss` | No reachable state has two agents each holding a valid (unexpired) lease. |
| `QueueFIFO` | The claim queue is exactly the not-yet-served tail of arrival order, so the seat is served in enqueue order. |
| `NoAppointByWatchdog` | Every history entry the watchdog writes (`by = "expire"`) closes a tenure — `expire` vacates, it never appoints. |
| `NoZombieAction` | The last boss action was taken under a valid lease; a past-TTL agent's boss-action is refused. |
| `MonotonicTime` | No recorded time is newer than the clock, and history times never decrease — a write never records a time older than the newest already recorded. |
| `AppendOnly` | `as_of_history` only grows: every step leaves it unchanged or appends exactly one entry. |

The operations are exactly the runtime's: `join` (first continuer into an empty
room), `renew`, `enqueue`, `take-seat` (front of the queue only), `expire` (the
watchdog path — vacate, never appoint), `zombie-reject` (a woken past-TTL boss
re-queues at the end), and `boss-action` (ACCEPT/REJECT). `Tick` advances the
clock; the seat is untouched.

`AppendOnly` is a **temporal (action) property** — it constrains transitions,
not a single state — so it is listed under `PROPERTY`, not `INVARIANTS`. The
other six are state invariants.

### Running it

```bash
java -cp tla2tools.jar tlc2.TLC -config seat.cfg seat.tla
```

Expected output ends with:

```
Model checking completed. No error has been found.
```

`Agents = {a1, a2, a3}`, `TimeMax = 3`, `TTL = 2` in `seat.cfg` is enough to
cover the protocol:

- **Three agents** is the smallest set in which the claim queue can hold more
  than one waiting claimant — with two, the single non-boss agent is the only
  possible claimant, so a multi-element queue (the case that makes FIFO order
  observable) is unreachable.
- **The clock `0..3` with `TTL = 2`** reaches every lease state. A lease taken
  at `t = 0` is valid through `t = 2` (the boundary `now = hb + TTL`) and past
  TTL at `t = 3`, so both a valid-lease boss-action and a zombie are reachable,
  and the watchdog `expire` fires. With `TimeMax = 2` expiry would be
  unreachable and `NoAppointByWatchdog` would be vacuously true.

### Scope and limits

- The model covers the **protocol's** safety, not the claim record's bytes. The
  atomic write/read of the claim file and the frozen append-only history view
  are exercised by [`../tests/test_coordination.py`](../tests/test_coordination.py)
  and [`../tests/test_coordination_failures.py`](../tests/test_coordination_failures.py),
  not here.
- It proves the rules are safe **as specified**. A runtime that appends to
  history before validating the lease, or that lets the watchdog appoint, is not
  caught by the model — the protocol tests are.
- It is **not** wired into CI: the pack is offline by design, and the checker is
  a ~4 MB jar, so there is no `tla2tools.jar` download step in
  `../.github/workflows/ci.yml`. Run it by hand with the command above.

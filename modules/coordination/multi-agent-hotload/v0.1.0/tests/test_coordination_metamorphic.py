"""Metamorphic relations for the seat state machine (SPEC.md section 8).

The example-based protocol suite (``test_coordination.py``) pins *specific*
outcomes: agent-a joins and agent-a is boss. That is necessary but brittle —
it cannot state the properties the protocol actually rests on, because those
are relations *between runs*, not values inside one run:

* the seat never reads an agent id's *content*, only its identity, so renaming
  every agent through a bijection must map every outcome (and every refusal);
* a lease is *relative* — shifting every timestamp by a constant must not
  change a single decision. A lease that had quietly become absolute (or
  anchored to a hardcoded epoch) would pass every example test and fail this
  one;
* FIFO means appending to the queue never moves the front, and never promotes
  an appended agent ahead of it;
* check-ins are re-delivered, so an operation applied twice must equal it
  applied once;
* as-of history only ever extends — it never shrinks and never rewrites an
  entry;
* the state machine is written against the ``ClaimStore`` interface, so the
  local-file store and the in-memory store must yield identical claims from an
  identical script — the metamorphic bridge between the two implementations.

Each relation is a different oracle from the example suite, and each can fail
independently, so this is a second opinion on the runtime rather than a
restatement of it. Deterministic injected clock, no LLM, no network; the
local-file cases are sequential (concurrency is the failure suite's job).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

# The ROLES.md example cast.
A = "agent-a@primary"
B = "agent-b@workstation"
C = "agent-c@laptop"
D = "agent-d@tablet"
E = "agent-e@phone"

# A bijection to rename the whole cast through (identity is not read).
RENAME = {A: "z-1@host", B: "z-2@host", C: "z-3@host", D: "z-4@host", E: "z-5@host"}

STORE_KINDS = ["local_file", "in_memory"]

# A full protocol script: appointment, renewal, lease expiry, FIFO queue,
# front-of-queue appointment, a zombie refusal, a zombie re-queue, a live-boss
# renewal, and a refusal while the seat is held. Exercised as one sequence so
# every relation below runs over the same load-bearing path set.
STEPS = [
    ("join", A, 0),
    ("renew", A, 10),
    ("expire", None, 40),        # A's lease lapsed: vacant, history appended
    ("enqueue", B, 41),
    ("enqueue", C, 42),
    ("take_seat", B, 43),        # front of the queue takes the seat
    ("boss_action", A, 44),      # refused: A is a zombie now
    ("zombie_reject", A, 44),    # A re-queues at the END
    ("renew", B, 50),
    ("enqueue", D, 51),          # refused: B holds the seat under a live lease
]

# The same shape but every operation succeeds — used where a spurious refusal
# must fail the test rather than be swallowed as an expected outcome.
SUCCESS_STEPS = [
    ("join", A, 0),
    ("renew", A, 10),
    ("expire", None, 40),
    ("enqueue", B, 41),
    ("enqueue", C, 42),
    ("take_seat", B, 43),
    ("zombie_reject", A, 44),
    ("renew", B, 50),
]


# ---------------------------------------------------------------------------
# Helpers: a scripted run and the two transformations


def make_machine(seat_protocol, kind: str, tmp_path, name: str):
    """A SeatMachine over a *fresh* store of ``kind`` (30m lease, as ROLES.md)."""
    if kind == "local_file":
        store = seat_protocol.LocalFileClaimStore(tmp_path / f"{name}.json")
    else:
        store = seat_protocol.InMemoryClaimStore()
    return seat_protocol.SeatMachine(store, lease_ttl_minutes=30)


def invoke(machine, op: str, agent, now):
    """Call one protocol operation by name (``expire`` takes no agent)."""
    method = getattr(machine, op)
    return method(now) if op == "expire" else method(agent, now)


def run_script(seat_protocol, machine, steps, base):
    """Run a script, recording each outcome as ``("ok", claim)`` or a refusal.

    A refusal is recorded as its *exception type name* only — never its
    message, which may quote an agent id and would make the renaming relation
    fail spuriously.
    """
    trace = []
    for op, agent, offset in steps:
        now = base + timedelta(minutes=offset)
        try:
            trace.append(("ok", invoke(machine, op, agent, now)))
        except seat_protocol.SeatError as exc:
            trace.append(("refused", type(exc).__name__))
    return trace


def final_claim(trace) -> dict:
    """The last claim an ``ok`` step produced (the seat's settled state)."""
    oks = [payload for kind, payload in trace if kind == "ok"]
    assert oks, "script produced no successful operation"
    return oks[-1]


def rename_claim(claim: dict, mapping: dict) -> dict:
    """Apply an agent-id bijection to every place a claim names an agent."""
    def r(x):
        return None if x is None else mapping.get(x, x)

    return dict(
        claim,
        who_is_boss_now=r(claim.get("who_is_boss_now")),
        claim_queue=[r(a) for a in claim.get("claim_queue", [])],
        as_of_history=[
            dict(e, boss_agent_id=r(e["boss_agent_id"]))
            for e in claim.get("as_of_history", [])
        ],
    )


def rename_trace(trace, mapping: dict):
    return [
        ("ok", rename_claim(payload, mapping)) if kind == "ok" else (kind, payload)
        for kind, payload in trace
    ]


def shift_claim(seat_protocol, claim: dict, delta: timedelta) -> dict:
    """Translate every timestamp a claim carries by ``delta`` (None stays None)."""
    def s(v):
        return None if v is None else seat_protocol.iso(seat_protocol.parse_dt(v) + delta)

    return dict(
        claim,
        last_heartbeat=s(claim.get("last_heartbeat")),
        vacated_at=s(claim.get("vacated_at")),
        as_of_history=[
            dict(e, as_of=s(e.get("as_of")), ended_at=s(e.get("ended_at")))
            for e in claim.get("as_of_history", [])
        ],
    )


def shift_trace(seat_protocol, trace, delta: timedelta):
    return [
        ("ok", shift_claim(seat_protocol, payload, delta)) if kind == "ok" else (kind, payload)
        for kind, payload in trace
    ]


# ---------------------------------------------------------------------------
# (a) Agent renaming: a bijection over ids maps every outcome


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_renaming_every_agent_maps_every_outcome(seat_protocol, tmp_path, clock, kind):
    original = run_script(
        seat_protocol, make_machine(seat_protocol, kind, tmp_path, "orig"), STEPS, clock.now
    )
    renamed_steps = [(op, None if a is None else RENAME[a], off) for op, a, off in STEPS]
    renamed = run_script(
        seat_protocol, make_machine(seat_protocol, kind, tmp_path, "renamed"), renamed_steps, clock.now
    )
    assert renamed == rename_trace(original, RENAME)
    # non-vacuity: the relation compared a run in which the ids really differ
    assert original != renamed
    assert final_claim(renamed)["who_is_boss_now"] == RENAME[B]
    assert final_claim(renamed)["claim_queue"] == [RENAME[C], RENAME[A]]


def test_renaming_leaves_an_unnamed_claim_unchanged(seat_protocol):
    """A vacant, empty claim has no agent to rename: the map is a no-op there."""
    vacant = seat_protocol.normalise_claim(None)
    assert rename_claim(vacant, RENAME) == vacant


# ---------------------------------------------------------------------------
# (b) Time translation: the lease is relative, so a shift changes no decision


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_shifting_every_timestamp_preserves_every_decision(seat_protocol, tmp_path, clock, kind):
    delta = timedelta(minutes=397)  # ~6h37m: crosses the TTL boundary either way
    base = clock.now
    original = run_script(
        seat_protocol, make_machine(seat_protocol, kind, tmp_path, "t0"), STEPS, base
    )
    shifted = run_script(
        seat_protocol, make_machine(seat_protocol, kind, tmp_path, "t1"), STEPS, base + delta
    )
    assert shifted == shift_trace(seat_protocol, original, delta)
    # non-vacuity: the shifted run's stamps really moved
    assert final_claim(shifted)["last_heartbeat"] != final_claim(original)["last_heartbeat"]
    # and the decisions themselves are identical, not merely shifted
    assert [k for k, _ in shifted] == [k for k, _ in original]


def test_a_shift_across_the_ttl_boundary_keeps_the_verdict(seat_protocol, tmp_path, clock):
    """A lease that has just lapsed stays lapsed under any translation of now."""
    delta = timedelta(minutes=100000)  # a long way away; still relative
    base = clock.now

    def verdict(machine, at):
        machine.join(A, at)
        return machine.enqueue(B, at + timedelta(minutes=31))  # 31 > 30 TTL: allowed

    here = verdict(make_machine(seat_protocol, "in_memory", tmp_path, "v0"), base)
    there = verdict(make_machine(seat_protocol, "in_memory", tmp_path, "v1"), base + delta)
    assert here["claim_queue"] == there["claim_queue"] == [B]


# ---------------------------------------------------------------------------
# (c) Queue extension: appending never changes (or promotes past) the front


def test_appending_agents_never_changes_the_front(machine, clock):
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    machine.enqueue(C, clock.advance(1))
    original = machine.status()["claim_queue"]
    assert original == [B, C]

    machine.enqueue(D, clock.advance(1))
    machine.enqueue(E, clock.advance(1))
    extended = machine.status()["claim_queue"]

    assert extended[0] == original[0] == B          # front unmoved
    assert extended[: len(original)] == original    # original order preserved
    assert extended == [B, C, D, E]


def test_appending_never_promotes_an_appended_agent(machine, seat_protocol, clock):
    """The strengthened form: after extension the *same* agent still takes the
    seat, and an appended agent cannot jump ahead of it."""
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    machine.enqueue(D, clock.advance(1))  # appended behind B

    # D is not the front and is refused
    with pytest.raises(seat_protocol.NotFrontOfQueueError):
        machine.take_seat(D, clock.advance(1))
    claim = machine.take_seat(B, clock.advance(1))
    assert claim["who_is_boss_now"] == B
    assert claim["claim_queue"] == [D]


# ---------------------------------------------------------------------------
# (d) Idempotent replay: applying an operation twice equals applying it once


def test_enqueue_replay_lands_one_entry(machine, clock):
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    raw_once = machine.store.read_raw()
    machine.enqueue(B, clock.advance(1))  # duplicate check-in, same instant
    assert machine.store.read_raw() == raw_once


def test_renew_replay_does_not_rewrite(machine, clock):
    machine.join(A, clock.now)
    machine.renew(A, clock.advance(10))
    raw_once = machine.store.read_raw()
    machine.renew(A, clock.advance(0))  # same instant re-delivered
    assert machine.store.read_raw() == raw_once


def test_expire_replay_does_not_rewrite(machine, clock):
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    raw_once = machine.store.read_raw()
    machine.expire(clock.advance(0))
    machine.expire(clock.advance(5))  # and later, still a no-op
    assert machine.store.read_raw() == raw_once


def test_zombie_reject_replay_queues_once(machine, clock):
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    machine.take_seat(B, clock.advance(1))
    machine.zombie_reject(A, clock.advance(1))
    raw_once = machine.store.read_raw()
    machine.zombie_reject(A, clock.advance(1))
    assert machine.store.read_raw() == raw_once


def test_take_seat_by_the_current_holder_is_a_noop(machine, clock):
    machine.join(A, clock.now)
    raw_once = machine.store.read_raw()
    machine.take_seat(A, clock.advance(1))  # A already holds the seat
    assert machine.store.read_raw() == raw_once


def test_join_replay_appoints_once(machine, clock):
    machine.join(A, clock.now)
    raw_once = machine.store.read_raw()
    machine.join(A, clock.advance(1))
    assert machine.store.read_raw() == raw_once


# ---------------------------------------------------------------------------
# (e) Monotonic history: extends, never shrinks, never rewrites


def test_history_prefix_extends_across_every_successful_operation(machine, clock):
    base = clock.now
    previous: list = []
    for op, agent, offset in SUCCESS_STEPS:
        invoke(machine, op, agent, base + timedelta(minutes=offset))
        history = machine.status()["as_of_history"]
        assert history[: len(previous)] == previous  # recorded prefix untouched
        assert len(history) >= len(previous)        # never shrinks
        previous = history
    # the seat changed three times: appoint A, end A's term, appoint B
    assert [e["boss_agent_id"] for e in previous] == [A, A, B]


def test_a_refused_operation_never_touches_history(machine, seat_protocol, clock):
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    machine.take_seat(B, clock.advance(1))
    before = machine.status()["as_of_history"]
    with pytest.raises(seat_protocol.ZombieBossError):
        machine.boss_action(A, clock.advance(1))
    with pytest.raises(seat_protocol.ZombieBossError):
        machine.renew(A, clock.advance(1))
    assert machine.status()["as_of_history"] == before


# ---------------------------------------------------------------------------
# (f) Store equivalence: the metamorphic bridge between the two stores


def test_the_two_stores_agree_on_an_identical_script(seat_protocol, tmp_path, clock):
    """Same operations, same clock, different persistence -> same claim.

    The script includes a lease expiry, a front-of-queue appointment and two
    refusals, so the bridge is load-bearing: a store that dropped a field or
    ordered a write differently would diverge here.
    """
    local = make_machine(seat_protocol, "local_file", tmp_path, "local")
    memory = make_machine(seat_protocol, "in_memory", tmp_path, "memory")
    local_trace = run_script(seat_protocol, local, STEPS, clock.now)
    memory_trace = run_script(seat_protocol, memory, STEPS, clock.now)
    assert local_trace == memory_trace

    local_claim = seat_protocol.normalise_claim(local.store.read_raw())
    memory_claim = seat_protocol.normalise_claim(memory.store.read_raw())
    assert local_claim == memory_claim
    # non-vacuity: the script really moved the seat and the queue
    assert local_claim["who_is_boss_now"] == B
    assert local_claim["claim_queue"] == [C, A]


# ---------------------------------------------------------------------------
# (g) Independent-operation commutation


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_independent_enqueues_commute_on_the_seat(seat_protocol, tmp_path, clock, kind):
    """Two enqueues of distinct agents touch no seat field, so they commute on
    the seat decision and on queue *membership*.

    Arrival order is deliberately excluded: ``claim_queue`` is FIFO, so the two
    orders must yield opposite queue orders — asserting equality there would be
    asserting a bug.
    """
    base = clock.now
    m1 = make_machine(seat_protocol, kind, tmp_path, "order1")
    m2 = make_machine(seat_protocol, kind, tmp_path, "order2")
    for m in (m1, m2):
        m.join(A, base)
        m.expire(base + timedelta(minutes=31))
    at = base + timedelta(minutes=32)

    m1.enqueue(B, at)
    first = m1.enqueue(C, at)
    m2.enqueue(C, at)
    second = m2.enqueue(B, at)

    assert (first["who_is_boss_now"], first["status"]) == (
        second["who_is_boss_now"],
        second["status"],
    ) == (None, "vacant")
    assert sorted(first["claim_queue"]) == sorted(second["claim_queue"]) == [B, C]
    # the order-sensitive part really is order-sensitive (non-vacuity)
    assert first["claim_queue"][0] != second["claim_queue"][0]


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_renew_and_requeue_of_distinct_agents_fully_commute(seat_protocol, tmp_path, clock, kind):
    """A live boss renewing and a non-holder re-queueing touch disjoint fields,
    so the two orders produce byte-for-byte the same claim."""
    base = clock.now
    at = base + timedelta(minutes=5)

    m1 = make_machine(seat_protocol, kind, tmp_path, "seq1")
    m1.join(A, base)
    m1.renew(A, at)
    first = m1.zombie_reject(B, at)

    m2 = make_machine(seat_protocol, kind, tmp_path, "seq2")
    m2.join(A, base)
    m2.zombie_reject(B, at)
    second = m2.renew(A, at)

    assert first == second
    # non-vacuity: both operations took effect
    assert first["who_is_boss_now"] == A
    assert first["claim_queue"] == [B]
    assert first["last_heartbeat"] == seat_protocol.iso(at)

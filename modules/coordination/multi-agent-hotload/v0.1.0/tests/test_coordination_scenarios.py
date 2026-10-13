"""The ROLES.md narrative as executable given/when/then scenarios.

ROLES.md is the binding prose spec, and the protocol/failure suites prove the
state machine's transitions in isolation. Neither reads the way an operator
learns the protocol: *the room fills in join order*; *a boss misses its lease
and a claimant takes the seat*; *the old boss wakes as a zombie, is refused,
and re-queues at the end*; *two claimants race and the queue is FIFO*. Those
sentences are the contract people actually reason about, so they get their own
tests here — a change that keeps the unit transitions green while breaking the
story a human was told fails in this file.

The pack is stdlib-only (no ``pytest-bdd``, no third-party dependencies), so a
"scenario" is an ordinary pytest function whose name reads as the sentence and
whose body is marked with the three beats (``# given`` / ``# when`` / ``# then``)
rather than a framework. Each scenario runs against the ``machine`` fixture,
which is parametrised over both ``ClaimStore`` implementations, and drives a
deterministic injected clock — no LLM, no network, Windows-safe.
"""

from __future__ import annotations

import pytest

# The ROLES.md example cast (illustrative ids; the seat ignores their text).
A = "agent-a@primary"      # first to continue -> decision boss
B = "agent-b@workstation"  # second -> coder1
C = "agent-c@laptop"       # third -> coder2


# ---------------------------------------------------------------------------
# Scenario 1: a fresh room fills in join order


def test_given_a_fresh_room_when_agents_join_in_order_then_the_first_is_boss(
    machine, clock
):
    # given a fresh, vacant room
    assert machine.status()["who_is_boss_now"] is None

    # when agents join in order
    machine.join(A, clock.now)
    machine.join(B, clock.advance(1))
    claim = machine.join(C, clock.advance(1))

    # then the first continuer is the decision boss and the later joiners are
    # workers: joining is not queueing, and it never disturbs the seat
    assert claim["who_is_boss_now"] == A
    assert claim["status"] == "held"
    assert claim["claim_queue"] == []
    assert [e["boss_agent_id"] for e in claim["as_of_history"]] == [A]


# ---------------------------------------------------------------------------
# Scenario 2: the boss misses its lease and a claimant takes the seat


def test_given_a_sitting_boss_when_its_lease_lapses_then_a_claimant_takes_the_seat(
    machine, clock
):
    # given a boss holding the seat under a lease
    machine.join(A, clock.now)

    # when the lease TTL (30m) lapses with no renewal, so the watchdog marks
    # the seat vacant...
    expired = machine.expire(clock.advance(31))
    assert expired["status"] == "vacant"
    assert expired["who_is_boss_now"] is None

    # ...and a claimant queues and takes the seat from the front
    machine.enqueue(B, clock.advance(1))
    claim = machine.take_seat(B, clock.advance(1))

    # then the claimant is the new boss, and as-of history records both terms
    assert claim["who_is_boss_now"] == B
    assert claim["status"] == "held"
    assert [e["boss_agent_id"] for e in claim["as_of_history"]] == [A, A, B]


# ---------------------------------------------------------------------------
# Scenario 3: a stale watchdog flag alone does not hand the seat over


def test_given_a_lease_still_within_ttl_when_the_watchdog_runs_then_the_seat_is_held(
    machine, clock
):
    # given a boss whose heartbeat is still inside the lease TTL
    machine.join(A, clock.now)

    # when the liveness watchdog runs (its only seat-facing power is expire)
    claim = machine.expire(clock.advance(10))

    # then the seat is untouched: the watchdog flags, it never appoints or vacates
    assert claim["who_is_boss_now"] == A
    assert claim["status"] == "held"


def test_given_a_vacant_seat_when_the_watchdog_runs_then_it_does_not_appoint(
    machine, clock
):
    # given a boss that lapsed with a claimant already queued
    machine.join(A, clock.now)
    machine.enqueue(B, clock.advance(60))  # queues behind a stale lease
    machine.expire(clock.advance(1))

    # when the watchdog runs again over the now-vacant seat
    claim = machine.expire(clock.advance(1))

    # then the claimant is still only queued -- appointment is an agent action
    assert claim["who_is_boss_now"] is None
    assert claim["claim_queue"] == [B]


# ---------------------------------------------------------------------------
# Scenario 4: the old boss returns as a zombie, refused then re-queued at the end


def test_given_a_dethroned_boss_when_it_wakes_then_it_is_refused_and_requeued_at_the_end(
    machine, seat_protocol, clock
):
    # given the old boss lost the seat to a claimant, with another waiting
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))
    machine.enqueue(B, clock.advance(1))
    machine.enqueue(C, clock.advance(1))
    machine.take_seat(B, clock.advance(1))

    # when the old boss wakes and tries a boss-only action, then a renewal
    with pytest.raises(seat_protocol.ZombieBossError):
        machine.boss_action(A, clock.advance(1))
    with pytest.raises(seat_protocol.ZombieBossError):
        machine.renew(A, clock.advance(1))

    # then it re-queues at the END -- no automatic reclaim, head never reordered
    claim = machine.zombie_reject(A, clock.advance(1))
    assert claim["who_is_boss_now"] == B  # the new boss is untouched
    assert claim["claim_queue"] == [C, A]


# ---------------------------------------------------------------------------
# Scenario 5: two claimants race and the queue is FIFO


def test_given_two_claimants_when_they_queue_then_the_front_takes_the_seat_fifo(
    machine, seat_protocol, clock
):
    # given a vacant seat after the boss's lease lapsed
    machine.join(A, clock.now)
    machine.expire(clock.advance(31))

    # when two claimants arrive, B first
    machine.enqueue(B, clock.advance(1))
    claim = machine.enqueue(C, clock.advance(1))

    # then the queue is FIFO by arrival order
    assert claim["claim_queue"] == [B, C]

    # and a non-front claimant cannot jump the queue
    with pytest.raises(seat_protocol.NotFrontOfQueueError):
        machine.take_seat(C, clock.advance(1))

    # the front takes the seat; the rest keep their order
    claim = machine.take_seat(B, clock.advance(1))
    assert claim["who_is_boss_now"] == B
    assert claim["claim_queue"] == [C]

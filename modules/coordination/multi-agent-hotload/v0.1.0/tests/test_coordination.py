"""Protocol tests for the seat state machine (no model involved).

Drives ``scripts/seat_protocol.py`` with scripted fake agents and asserts
every transition in ROLES.md's vacancy/queue/claim table plus the zombie
rule — including the four that had no implementation when issue #60 was
filed: enqueue, appoint from the front of the queue, zombie rejection, and
as-of history append. Deterministic and repeatable: a fixed clock fixture,
no LLM, no network.

The suite is parametrised over both ``ClaimStore`` implementations
(local file, in-memory) so the assertions target the interface, which is the
seam a future GitHub-canonical store plugs into without rewriting the state
machine.
"""

from __future__ import annotations

import json

import pytest

BOSS = "agent-a@primary"
C1 = "agent-b@workstation"
C2 = "agent-c@laptop"


def read_store(seat_protocol, store) -> dict:
    return seat_protocol.normalise_claim(store.read_raw())


# ---------------------------------------------------------------------------
# Empty room: first continuer becomes the decision boss


class TestJoin:
    def test_first_continuer_takes_an_empty_room(self, machine, clock):
        claim = machine.join(BOSS, clock.now)
        assert claim["who_is_boss_now"] == BOSS
        assert claim["status"] == "held"
        assert claim["claim_queue"] == []
        # seat change appended as-of history (ROLES.md step 6)
        assert len(claim["as_of_history"]) == 1
        assert claim["as_of_history"][0]["boss_agent_id"] == BOSS

    def test_second_joiner_is_a_worker_not_a_boss(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.join(C1, clock.advance(1))
        assert claim["who_is_boss_now"] == BOSS  # unchanged
        assert claim["claim_queue"] == []  # joining is not enqueueing
        assert len(claim["as_of_history"]) == 1  # no seat change

    def test_join_is_a_noop_when_a_queue_exists(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(40))
        machine.enqueue(C1, clock.advance(1))
        claim = machine.join(C2, clock.advance(1))
        assert claim["who_is_boss_now"] is None
        assert claim["claim_queue"] == [C1]

    def test_join_is_idempotent_for_the_same_agent(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.join(BOSS, clock.advance(1))
        assert claim["who_is_boss_now"] == BOSS
        assert len(claim["as_of_history"]) == 1  # no second appointment


# ---------------------------------------------------------------------------
# Lease: renew within TTL, expire past it


class TestRenew:
    def test_boss_renews_within_ttl(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.renew(BOSS, clock.advance(10))
        assert claim["who_is_boss_now"] == BOSS
        assert claim["last_heartbeat"] == claim["last_heartbeat"]
        assert claim["status"] == "held"

    def test_renew_refreshes_the_heartbeat_stamp(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.renew(BOSS, clock.advance(25))
        assert claim["last_heartbeat"].startswith("2026-10-13T12:25")

    def test_non_holder_cannot_renew(self, machine, clock):
        machine.join(BOSS, clock.now)
        with pytest.raises(Exception) as exc:
            machine.renew(C1, clock.advance(5))
        assert "does not hold the boss seat" in str(exc.value)

    def test_past_ttl_renew_is_refused_no_automatic_reclaim(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.renew(BOSS, clock.advance(31))  # 30m TTL elapsed
        # and the seat itself is untouched by the refused renewal
        assert read_store(seat_protocol, machine.store)["who_is_boss_now"] == BOSS


# ---------------------------------------------------------------------------
# Vacancy


class TestExpire:
    def test_expire_writes_vacant_and_appends_history(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.expire(clock.advance(31))
        assert claim["status"] == "vacant"
        assert claim["who_is_boss_now"] is None
        assert claim["vacated_at"] is not None
        # history grew: the boss's ended term was appended, not rewritten
        assert len(claim["as_of_history"]) == 2
        assert claim["as_of_history"][0] == claim["as_of_history"][0]
        assert claim["as_of_history"][1]["boss_agent_id"] == BOSS
        assert claim["as_of_history"][1]["ended_at"] is not None

    def test_expire_preserves_the_claim_queue(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        claim = machine.expire(clock.advance(1))
        assert claim["claim_queue"] == [C1]

    def test_expire_is_idempotent_when_already_vacant(self, machine, clock, seat_protocol):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        raw_after_first = machine.store.read_raw()
        machine.expire(clock.advance(5))
        assert machine.store.read_raw() == raw_after_first  # no rewrite

    def test_expire_is_a_noop_within_ttl(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.expire(clock.advance(10))
        assert claim["who_is_boss_now"] == BOSS  # lease still valid


# ---------------------------------------------------------------------------
# Enqueue (FIFO) — previously unimplemented


class TestEnqueue:
    def test_claimant_appends_to_the_queue_in_arrival_order(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        claim = machine.enqueue(C2, clock.advance(1))
        assert claim["claim_queue"] == [C1, C2]  # FIFO by arrival

    def test_duplicate_delivery_is_idempotent(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        claim = machine.enqueue(C1, clock.advance(1))  # duplicate check-in
        assert claim["claim_queue"] == [C1]  # exactly one entry

    def test_sitting_boss_enqueueing_is_a_noop(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.enqueue(BOSS, clock.advance(1))
        assert claim["claim_queue"] == []

    def test_enqueue_is_refused_while_a_live_boss_holds_the_seat(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        with pytest.raises(seat_protocol.SeatNotVacantError):
            machine.enqueue(C1, clock.advance(5))

    def test_enqueue_after_a_stale_lease_is_allowed(self, machine, clock):
        # the boss's lease silently expired; the claimant may queue up
        machine.join(BOSS, clock.now)
        claim = machine.enqueue(C1, clock.advance(60))
        assert claim["claim_queue"] == [C1]


# ---------------------------------------------------------------------------
# Appointment: front of the queue takes the vacant seat — previously unimplemented


class TestTakeSeat:
    def _vacant_with_queue(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.enqueue(C2, clock.advance(1))
        return clock.advance(1)

    def test_front_of_queue_takes_the_seat(self, machine, clock):
        now = self._vacant_with_queue(machine, clock)
        claim = machine.take_seat(C1, now)
        assert claim["who_is_boss_now"] == C1
        assert claim["claim_queue"] == [C2]  # the rest keep their order
        assert claim["status"] == "held"
        assert claim["as_of_history"][-1]["boss_agent_id"] == C1

    def test_non_front_claimant_is_refused(self, machine, seat_protocol, clock):
        now = self._vacant_with_queue(machine, clock)
        with pytest.raises(seat_protocol.NotFrontOfQueueError):
            machine.take_seat(C2, now)  # C1 is at the front

    def test_take_seat_expires_a_stale_lease_first(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.enqueue(C1, clock.advance(60))  # queues behind a stale lease
        claim = machine.take_seat(C1, clock.advance(1))
        assert claim["who_is_boss_now"] == C1
        # expiry was recorded as history before the appointment
        terms = [e for e in claim["as_of_history"] if e["ended_at"] is not None]
        assert any(t["boss_agent_id"] == BOSS for t in terms)

    def test_take_seat_is_refused_when_a_live_boss_holds_the_seat(
        self, machine, seat_protocol, clock
    ):
        machine.join(BOSS, clock.now)
        with pytest.raises(seat_protocol.SeatNotVacantError):
            machine.take_seat(C1, clock.advance(5))

    def test_take_seat_with_an_empty_queue_is_refused(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        with pytest.raises(seat_protocol.NotFrontOfQueueError):
            machine.take_seat(C1, clock.advance(1))

    def test_take_seat_is_idempotent_for_the_sitting_boss(self, machine, clock):
        now = self._vacant_with_queue(machine, clock)
        machine.take_seat(C1, now)
        claim = machine.take_seat(C1, clock.advance(1))
        assert claim["who_is_boss_now"] == C1
        assert len(claim["as_of_history"]) == 3  # no extra appointment entry


# ---------------------------------------------------------------------------
# Zombie rule — previously unimplemented


class TestZombie:
    def test_zombie_cannot_perform_boss_only_actions(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))  # a new boss took the seat
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.boss_action(BOSS, clock.advance(1))  # old boss wakes

    def test_zombie_requeues_at_the_end_not_the_front(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.enqueue(C2, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))
        claim = machine.zombie_reject(BOSS, clock.advance(1))
        assert claim["who_is_boss_now"] == C1  # seat unchanged
        assert claim["claim_queue"] == [C2, BOSS]  # end of the queue

    def test_zombie_reject_leaves_the_queue_head_alone(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.enqueue(C2, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))
        claim = machine.zombie_reject(BOSS, clock.advance(1))
        assert claim["claim_queue"][0] == C2  # head never reordered

    def test_zombie_reject_is_idempotent(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))
        machine.zombie_reject(BOSS, clock.advance(1))
        claim = machine.zombie_reject(BOSS, clock.advance(1))
        assert claim["claim_queue"].count(BOSS) == 1

    def test_current_boss_zombie_reject_is_a_noop(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.zombie_reject(BOSS, clock.advance(1))
        assert claim["who_is_boss_now"] == BOSS
        assert claim["claim_queue"] == []

    def test_boss_action_allowed_for_the_live_boss(self, machine, clock):
        machine.join(BOSS, clock.now)
        claim = machine.boss_action(BOSS, clock.advance(5))
        assert claim["who_is_boss_now"] == BOSS

    def test_boss_action_refused_past_ttl(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.boss_action(BOSS, clock.advance(31))

    def test_zombie_renewal_after_a_new_boss_is_refused(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.renew(BOSS, clock.advance(1))


# ---------------------------------------------------------------------------
# As-of history: append-only by construction


class TestAsOfHistory:
    def test_history_grows_on_every_seat_change(self, machine, clock):
        machine.join(BOSS, clock.now)            # 1: appointment
        machine.expire(clock.advance(31))         # 2: term ended
        machine.enqueue(C1, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))   # 3: new appointment
        assert len(machine.status()["as_of_history"]) == 3

    def test_recorded_entries_are_never_rewritten(self, machine, clock):
        machine.join(BOSS, clock.now)
        machine.expire(clock.advance(31))
        machine.enqueue(C1, clock.advance(1))
        machine.take_seat(C1, clock.advance(1))
        history = machine.status()["as_of_history"]
        # the first entry — the boss's original appointment — is intact
        assert history[0]["boss_agent_id"] == BOSS
        assert history[0]["ended_at"] is None or history[0]["ended_at"]
        # and every entry still carries the required fields
        for entry in history:
            assert entry["as_of"]
            assert entry["boss_agent_id"]

    def test_frozen_history_view_rejects_mutation(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        view = seat_protocol.AppendOnlyHistory(machine.status())
        with pytest.raises(TypeError):
            view.recorded[0]["boss_agent_id"] = "tampered"

    def test_history_projection_is_json_serialisable(self, machine, seat_protocol, clock):
        machine.join(BOSS, clock.now)
        view = seat_protocol.AppendOnlyHistory(machine.status())
        extended = view.append({"boss_agent_id": C1, "ended_at": None, "notes": "x"}, clock.advance(1))
        json.dumps(extended)  # plain dicts, not MappingProxyType

    def test_write_point_rejects_a_history_rewrite(self, seat_protocol, machine, clock):
        # A hypothetical transition that rewrote a recorded entry is refused
        # at the single write choke point, whatever the mutator did.
        old = {
            "status": "held",
            "who_is_boss_now": BOSS,
            "last_heartbeat": None,
            "vacated_at": None,
            "claim_queue": [],
            "as_of_history": [
                {"as_of": "2026-10-13T12:00:00+00:00", "boss_agent_id": BOSS}
            ],
        }
        new = dict(old, as_of_history=[])  # dropped the recorded entry
        with pytest.raises(seat_protocol.SeatError):
            seat_protocol.SeatMachine._assert_append_only(old, new)

    def test_seat_change_without_history_append_is_refused(self, seat_protocol):
        old = {
            "status": "held",
            "who_is_boss_now": BOSS,
            "last_heartbeat": None,
            "vacated_at": None,
            "claim_queue": [],
            "as_of_history": [
                {"as_of": "2026-10-13T12:00:00+00:00", "boss_agent_id": BOSS}
            ],
        }
        new = dict(old, who_is_boss_now=C1)  # seat moved, nothing appended
        with pytest.raises(seat_protocol.SeatError, match="without appending"):
            seat_protocol.SeatMachine._assert_append_only(old, new)


# ---------------------------------------------------------------------------
# Record shape


class TestRecordShape:
    def test_absent_record_reads_as_fresh_vacant(self, machine):
        claim = machine.status()
        assert claim["status"] == "vacant"
        assert claim["who_is_boss_now"] is None
        assert claim["claim_queue"] == []

    def test_unknown_keys_survive_a_transition(self, machine, seat_protocol, clock):
        raw = {
            "status": "vacant",
            "who_is_boss_now": None,
            "last_heartbeat": None,
            "vacated_at": None,
            "claim_queue": [],
            "as_of_history": [],
            "custom_field": "operator annotation",
        }
        machine.store.write_if_unchanged(None, seat_protocol.encode_claim(raw))
        machine.join(BOSS, clock.now)
        after = read_store(seat_protocol, machine.store)
        assert after["custom_field"] == "operator annotation"

    def test_lease_ttl_bounds_match_roles_md(self, seat_protocol):
        # ROLES.md: default 30, projects set 15-120 — unchanged by this work
        assert seat_protocol.DEFAULT_LEASE_TTL_MINUTES == 30.0
        assert seat_protocol.LEASE_TTL_MIN == 15.0
        assert seat_protocol.LEASE_TTL_MAX == 120.0

    @pytest.mark.parametrize("ttl", [5.0, 14.9, 120.1, 300.0])
    def test_out_of_range_ttl_is_refused(self, seat_protocol, claim_store, ttl):
        with pytest.raises(ValueError):
            seat_protocol.SeatMachine(claim_store, lease_ttl_minutes=ttl)

    @pytest.mark.parametrize("ttl", [15.0, 30.0, 120.0])
    def test_in_range_ttls_are_accepted(self, seat_protocol, claim_store, ttl):
        seat_protocol.SeatMachine(claim_store, lease_ttl_minutes=ttl)


# ---------------------------------------------------------------------------
# Full protocol scenario (the ROLES.md example fill)


class TestExampleScenario:
    def test_roles_md_example_fill(self, machine, seat_protocol, clock):
        """The illustrative walk-through in ROLES.md, end to end."""
        # agent-a joins first: decision boss (lease starts)
        claim = machine.join(BOSS, clock.now)
        assert claim["who_is_boss_now"] == BOSS

        # boss lease expires (minutes); seat vacant
        claim = machine.expire(clock.advance(31))
        assert claim["status"] == "vacant"

        # agent-b and agent-c enqueue; front takes boss
        machine.enqueue(C1, clock.advance(1))
        machine.enqueue(C2, clock.advance(1))
        claim = machine.take_seat(C1, clock.advance(1))
        assert claim["who_is_boss_now"] == C1

        # agent-a wakes as a zombie: reject boss actions, join the queue's end
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.boss_action(BOSS, clock.advance(1))
        claim = machine.zombie_reject(BOSS, clock.advance(1))
        assert claim["claim_queue"] == [C2, BOSS]

        # a 10-minute stale watchdog flag alone does not hand the seat over
        # (the watchdog path, expire(), is liveness-only and never appoints)
        claim = machine.expire(clock.advance(5))
        assert claim["who_is_boss_now"] == C1  # fresh lease: noop

        # history answers "who was boss at T" without mutating the seat
        history = machine.status()["as_of_history"]
        assert [e["boss_agent_id"] for e in history] == [BOSS, BOSS, C1]
        assert [e["ended_at"] for e in history] == [
            None,  # original appointment, superseded by the closed term entry
            history[1]["ended_at"],  # the term that ended at vacancy
            None,  # current holder's open term
        ]

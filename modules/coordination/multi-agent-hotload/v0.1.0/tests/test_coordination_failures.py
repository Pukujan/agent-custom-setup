"""Failure-path tests for the seat state machine (issue #60, Pass 2).

Six failure modes, each asserting the specified outcome:

1. duplicate delivery of the same check-in — idempotent, one queue entry;
2. two claimants enqueueing simultaneously — no lost update;
3. a zombie waking after a new boss took the seat — boss actions rejected;
4. a restart between vacancy and appointment — the durable front is appointed;
5. a clock that jumps backward — refused, nothing written;
6. a claim file that is corrupt or absent — fail closed / fresh vacant.

The watchdog delegation is exercised too: its seat-changing path
(``write_vacant``) must append as-of history and its lease evaluation must
agree with the runtime's.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

BOSS = "agent-a@primary"
C1 = "agent-b@workstation"
C2 = "agent-c@laptop"
T0 = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Duplicate delivery of the same check-in


class TestDuplicateDelivery:
    def test_duplicate_enqueue_lands_once(self, seat_protocol, tmp_path):
        store = seat_protocol.LocalFileClaimStore(tmp_path / "claim.json")
        machine = seat_protocol.SeatMachine(store, lease_ttl_minutes=30)
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        claim = machine.enqueue(C1, T0 + timedelta(minutes=32, seconds=5))
        assert claim["claim_queue"] == [C1]

    def test_duplicate_delivery_across_restarts(self, seat_protocol, tmp_path):
        """The same check-in redelivered by a fresh process (new store instance)."""
        path = tmp_path / "claim.json"
        seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        ).join(BOSS, T0)
        seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).expire(
            T0 + timedelta(minutes=31)
        )
        first = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path))
        first.enqueue(C1, T0 + timedelta(minutes=32))
        # the "duplicate" is a separate process reading what the first wrote
        second = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path))
        claim = second.enqueue(C1, T0 + timedelta(minutes=32, seconds=1))
        assert claim["claim_queue"] == [C1]

    def test_concurrent_duplicate_delivery_lands_once(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        ).join(BOSS, T0)
        seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).expire(
            T0 + timedelta(minutes=31)
        )
        errors: list[str] = []

        def deliver():
            try:
                seat_protocol.SeatMachine(
                    seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
                ).enqueue(C1, T0 + timedelta(minutes=32))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=deliver) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        claim = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()
        assert claim["claim_queue"] == [C1]


# ---------------------------------------------------------------------------
# 2. Two claimants enqueueing simultaneously


class TestSimultaneousClaimants:
    def test_no_lost_update_when_many_claimants_race(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        ).join(BOSS, T0)
        seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).expire(
            T0 + timedelta(minutes=31)
        )
        ids = [f"agent-{i}@race" for i in range(10)]
        errors: list[str] = []

        def claim(agent_id):
            try:
                seat_protocol.SeatMachine(
                    seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
                ).enqueue(agent_id, T0 + timedelta(minutes=32))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=claim, args=(a,)) for a in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        final = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()
        # every claimant is present exactly once: no lost update, no duplicate
        assert sorted(final["claim_queue"]) == sorted(ids)
        assert len(final["claim_queue"]) == len(ids)

    def test_queue_positions_are_distinct_and_unique(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        ).join(BOSS, T0)
        seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).expire(
            T0 + timedelta(minutes=31)
        )
        ids = [f"agent-{i}@race" for i in range(6)]
        errors: list[str] = []

        def claim(agent_id):
            try:
                seat_protocol.SeatMachine(
                    seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
                ).enqueue(agent_id, T0 + timedelta(minutes=32))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=claim, args=(a,)) for a in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        queue = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()[
            "claim_queue"
        ]
        assert len(set(queue)) == len(queue)  # FIFO positions are unique


# ---------------------------------------------------------------------------
# 3. A zombie waking after a new boss took the seat


class TestZombieWake:
    def test_zombie_rejected_at_every_boss_only_operation(self, seat_protocol, tmp_path):
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        machine.take_seat(C1, T0 + timedelta(minutes=33))
        wake = T0 + timedelta(minutes=40)

        with pytest.raises(seat_protocol.ZombieBossError):
            machine.boss_action(BOSS, wake)  # ACCEPT/REJECT refused
        with pytest.raises(seat_protocol.ZombieBossError):
            machine.renew(BOSS, wake)  # renewing as boss refused

    def test_zombie_requeue_does_not_steal_the_seat_back(self, seat_protocol, tmp_path):
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        machine.enqueue(C2, T0 + timedelta(minutes=33))
        machine.take_seat(C1, T0 + timedelta(minutes=34))

        claim = machine.zombie_reject(BOSS, T0 + timedelta(minutes=40))
        assert claim["who_is_boss_now"] == C1  # the new boss is untouched
        assert claim["claim_queue"] == [C2, BOSS]  # zombie joins the end
        # and history still records both terms, unchanged
        assert [e["boss_agent_id"] for e in claim["as_of_history"]] == [BOSS, BOSS, C1]

    def test_zombie_then_expiry_keeps_fifo_order(self, seat_protocol, tmp_path):
        """After the new boss also goes silent, the queue (with the zombie at
        its end) still appoints in FIFO order."""
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        machine.take_seat(C1, T0 + timedelta(minutes=33))
        machine.zombie_reject(BOSS, T0 + timedelta(minutes=34))

        machine.expire(T0 + timedelta(minutes=70))  # C1's lease lapses too
        claim = machine.take_seat(BOSS, T0 + timedelta(minutes=71))
        assert claim["who_is_boss_now"] == BOSS  # FIFO: zombie was the only one queued


# ---------------------------------------------------------------------------
# 4. A restart between vacancy and appointment


class TestRestartMidClaim:
    def test_state_survives_a_restart_between_vacancy_and_appointment(
        self, seat_protocol, tmp_path
    ):
        path = tmp_path / "claim.json"
        # process 1: boss joins, lease expires, two claimants queue up, then
        # the process dies before anyone takes the seat
        m1 = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30)
        m1.join(BOSS, T0)
        m1.expire(T0 + timedelta(minutes=31))
        m1.enqueue(C1, T0 + timedelta(minutes=32))
        m1.enqueue(C2, T0 + timedelta(minutes=33))

        # process 2 (a "restart"): fresh store + fresh machine over the same path
        m2 = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30)
        status = m2.status()
        assert status["status"] == "vacant"
        assert status["claim_queue"] == [C1, C2]  # the queue survived

        claim = m2.take_seat(C1, T0 + timedelta(minutes=60))
        assert claim["who_is_boss_now"] == C1
        assert claim["claim_queue"] == [C2]
        # history survived too: the restart did not reset the record of terms
        assert [e["boss_agent_id"] for e in claim["as_of_history"]] == [BOSS, BOSS, C1]

    def test_vacancy_itself_survives_a_restart(self, seat_protocol, tmp_path):
        """A vacancy written before the crash is still vacant after it — the
        record on disk, not a process's memory, is the seat state."""
        path = tmp_path / "claim.json"
        m1 = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30)
        m1.join(BOSS, T0)
        m1.expire(T0 + timedelta(minutes=31))

        m2 = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30)
        assert m2.status()["who_is_boss_now"] is None


# ---------------------------------------------------------------------------
# 5. A clock that jumps backward


class TestClockRegression:
    def test_backwards_clock_refuses_to_write(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        raw_before = path.read_bytes()

        with pytest.raises(seat_protocol.ClockRegressionError):
            machine.renew(BOSS, T0 - timedelta(minutes=5))

        assert path.read_bytes() == raw_before  # nothing written

    def test_backwards_clock_refuses_even_a_noop_transition(self, seat_protocol, tmp_path):
        """A rewound clock is refused before the mutator runs.

        Under a rewound clock a stale lease *looks* fresh (the age is
        negative), so an expiry that should have fired becomes a silent
        no-op. That is the state an old boss would want to smuggle through,
        so the guard must fire on the clock alone — not only when the
        transition happens to change the record.
        """
        path = tmp_path / "claim.json"
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        raw_before = path.read_bytes()
        with pytest.raises(seat_protocol.ClockRegressionError):
            machine.expire(T0 - timedelta(hours=1))
        assert path.read_bytes() == raw_before  # nothing written

    def test_backwards_clock_cannot_rewrite_a_renewal(self, seat_protocol, tmp_path):
        """The attack the guard exists to stop: an old boss whose seat was
        lost uses a rewound clock to push its heartbeat *backwards* —
        rewriting a recorded time — which would resurrect an expired lease."""
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        join = datetime(2026, 10, 13, 11, 20, tzinfo=timezone.utc)
        renew_at = datetime(2026, 10, 13, 11, 50, tzinfo=timezone.utc)
        machine.join(BOSS, join)
        machine.renew(BOSS, renew_at)  # recorded heartbeat: 11:50
        # a rewound "now" of 11:20 predates the recorded 11:50 stamp
        with pytest.raises(seat_protocol.ClockRegressionError):
            machine.renew(BOSS, join)
        # the recorded heartbeat was not rewound
        assert machine.status()["last_heartbeat"] == renew_at.isoformat()

    def test_a_rewind_below_every_recorded_stamp_is_refused(self, seat_protocol, tmp_path):
        """Whatever the operation, `now` may never precede the newest stamp
        the claim already records (heartbeat, vacated_at, history entries)."""
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        # recorded stamps reach 12:31 (vacated_at); 12:10 predates them
        for op, agent in (("expire", None), ("enqueue", C2), ("take_seat", C1)):
            with pytest.raises(seat_protocol.ClockRegressionError):
                if agent is None:
                    machine.expire(T0 + timedelta(minutes=10))
                else:
                    getattr(machine, op)(agent, T0 + timedelta(minutes=10))

    def test_backwards_clock_refuses_enqueue_too(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        machine.expire(T0 + timedelta(minutes=31))
        machine.enqueue(C1, T0 + timedelta(minutes=32))
        raw_before = path.read_bytes()

        with pytest.raises(seat_protocol.ClockRegressionError):
            machine.enqueue(C2, T0 + timedelta(minutes=30))  # before the vacancy stamp
        assert path.read_bytes() == raw_before

    def test_recovered_clock_resumes_normally(self, seat_protocol, tmp_path):
        """A refused rewind does not wedge the seat: once the clock is sane
        again, transitions proceed."""
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "claim.json"), lease_ttl_minutes=30
        )
        machine.join(BOSS, T0)
        with pytest.raises(seat_protocol.ClockRegressionError):
            machine.renew(BOSS, T0 - timedelta(minutes=1))
        claim = machine.renew(BOSS, T0 + timedelta(minutes=1))
        assert claim["who_is_boss_now"] == BOSS

    def test_future_dated_stale_lock_does_not_deadlock(self, seat_protocol, tmp_path, monkeypatch):
        """A lock file whose mtime is far in the future (clock regressed after
        creation) is broken promptly instead of blocking forever."""
        import os
        import time

        path = tmp_path / "claim.json"
        store = seat_protocol.LocalFileClaimStore(path)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_bytes(b"{}")
        store.lock_path.write_bytes(b"")
        future = time.time() + 3600  # an hour "ahead"
        os.utime(store.lock_path, (future, future))
        started = time.monotonic()
        assert store.read_raw() == b"{}"
        assert time.monotonic() - started < 5  # did not wait out the deadline


# ---------------------------------------------------------------------------
# 6. A claim file that is corrupt or absent


class TestCorruptOrAbsentClaim:
    def test_corrupt_json_fails_closed_and_is_left_untouched(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        path.write_bytes(b"{ this is not json")
        with pytest.raises(seat_protocol.CorruptClaimFileError):
            seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()
        assert path.read_bytes() == b"{ this is not json"  # untouched

    def test_non_object_json_fails_closed(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        path.write_bytes(b'["a list"]')
        with pytest.raises(seat_protocol.CorruptClaimFileError):
            seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()

    def test_corrupt_claim_blocks_transitions(self, seat_protocol, tmp_path):
        """No operation may "recover" by overwriting a record it cannot parse."""
        path = tmp_path / "claim.json"
        path.write_bytes(b"{ broken")
        machine = seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=30)
        for op in ("join", "renew", "enqueue", "take_seat", "expire", "zombie_reject"):
            with pytest.raises(seat_protocol.CorruptClaimFileError):
                if op == "expire":
                    machine.expire(T0)
                else:
                    getattr(machine, op)(C1, T0)
        assert path.read_bytes() == b"{ broken"

    def test_absent_claim_is_a_fresh_vacant_seat(self, seat_protocol, tmp_path):
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "never-written.json"), lease_ttl_minutes=30
        )
        claim = machine.status()
        assert claim["status"] == "vacant"
        assert claim["who_is_boss_now"] is None

    def test_transitions_work_on_an_absent_claim(self, seat_protocol, tmp_path):
        """First use creates the record: enqueue then take_seat on a fresh seat."""
        machine = seat_protocol.SeatMachine(
            seat_protocol.LocalFileClaimStore(tmp_path / "fresh.json"), lease_ttl_minutes=30
        )
        machine.enqueue(C1, T0)
        claim = machine.take_seat(C1, T0 + timedelta(minutes=1))
        assert claim["who_is_boss_now"] == C1
        assert len(claim["as_of_history"]) == 1

    def test_malformed_queue_fails_closed(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        path.write_text(json.dumps({"claim_queue": "not-a-list"}), encoding="utf-8")
        with pytest.raises(seat_protocol.CorruptClaimFileError):
            seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()

    def test_malformed_history_fails_closed(self, seat_protocol, tmp_path):
        path = tmp_path / "claim.json"
        path.write_text(json.dumps({"as_of_history": [42]}), encoding="utf-8")
        with pytest.raises(seat_protocol.CorruptClaimFileError):
            seat_protocol.SeatMachine(seat_protocol.LocalFileClaimStore(path)).status()


# ---------------------------------------------------------------------------
# Watchdog delegation (the pack's one pre-existing seat-changing path)


class TestWatchdogDelegation:
    @pytest.fixture
    def watchdog(self):
        from importlib.util import module_from_spec, spec_from_file_location

        script = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "scripts" / "watchdog_check.py"
        )
        spec = spec_from_file_location("watchdog_check_deleg", script)
        assert spec and spec.loader
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_write_vacant_appends_history_and_keeps_the_queue(self, watchdog, tmp_path):
        path = tmp_path / "claim.json"
        path.write_text(
            json.dumps(
                {
                    "status": "held",
                    "who_is_boss_now": BOSS,
                    "last_heartbeat": (T0 - timedelta(minutes=45)).isoformat(),
                    "claim_queue": [C1, C2],
                    "as_of_history": [
                        {"as_of": T0.isoformat(), "boss_agent_id": BOSS, "ended_at": None}
                    ],
                }
            ),
            encoding="utf-8",
        )
        claim = json.loads(path.read_text(encoding="utf-8"))
        watchdog.write_vacant(path, dict(claim, lease_ttl_minutes=30.0), now=T0)
        after = json.loads(path.read_text(encoding="utf-8"))
        assert after["status"] == "vacant"
        assert after["who_is_boss_now"] is None
        assert after["claim_queue"] == [C1, C2]
        assert len(after["as_of_history"]) == 2  # the term was appended
        assert after["as_of_history"][0] == claim["as_of_history"][0]  # intact

    def test_write_vacant_is_idempotent(self, watchdog, tmp_path):
        path = tmp_path / "claim.json"
        path.write_text(
            json.dumps(
                {
                    "status": "held",
                    "who_is_boss_now": BOSS,
                    "last_heartbeat": (T0 - timedelta(minutes=45)).isoformat(),
                    "claim_queue": [],
                    "as_of_history": [],
                }
            ),
            encoding="utf-8",
        )
        watchdog.write_vacant(path, {"lease_ttl_minutes": 30.0}, now=T0)
        raw = path.read_bytes()
        watchdog.write_vacant(path, {"lease_ttl_minutes": 30.0}, now=T0 + timedelta(minutes=1))
        assert path.read_bytes() == raw

    def test_write_vacant_respects_a_fresh_lease(self, watchdog, tmp_path):
        """The watchdog cannot vacate a seat whose heartbeat is within TTL."""
        path = tmp_path / "claim.json"
        path.write_text(
            json.dumps(
                {
                    "status": "held",
                    "who_is_boss_now": BOSS,
                    "last_heartbeat": (T0 - timedelta(minutes=5)).isoformat(),
                    "claim_queue": [],
                    "as_of_history": [],
                }
            ),
            encoding="utf-8",
        )
        watchdog.write_vacant(path, {"lease_ttl_minutes": 30.0}, now=T0)
        assert json.loads(path.read_text(encoding="utf-8"))["who_is_boss_now"] == BOSS

    def test_watchdog_never_appoints(self, watchdog, tmp_path):
        """The watchdog's whole vocabulary is expire: a queued claimant stays
        queued after the watchdog runs — appointment is an agent operation."""
        path = tmp_path / "claim.json"
        path.write_text(
            json.dumps(
                {
                    "status": "held",
                    "who_is_boss_now": BOSS,
                    "last_heartbeat": (T0 - timedelta(minutes=45)).isoformat(),
                    "claim_queue": [C1],
                    "as_of_history": [],
                }
            ),
            encoding="utf-8",
        )
        rc = watchdog.main(["--claim-file", str(path)])
        assert rc == 0
        after = json.loads(path.read_text(encoding="utf-8"))
        assert after["who_is_boss_now"] is None  # vacated, yes...
        assert after["claim_queue"] == [C1]  # ...but nobody appointed

    def test_evaluate_agrees_with_the_runtime_lease(self, watchdog, seat_protocol):
        """The watchdog's vacant decision is exactly the runtime's lease check."""
        for age in (0, 5, 15, 29.9, 30, 30.1, 45, 120):
            hb = T0 - timedelta(minutes=age)
            got = watchdog.evaluate(
                last_heartbeat=hb,
                last_github_activity=None,
                lease_ttl_minutes=30,
                idle_window_minutes=20,
                now=T0,
            )
            lease_valid = seat_protocol.evaluate_lease(hb, 30.0, T0)
            assert (got == "vacant") == (not lease_valid), f"age={age}: {got}"

    def test_main_dry_run_writes_nothing(self, watchdog, tmp_path):
        path = tmp_path / "claim.json"
        path.write_text(
            json.dumps(
                {
                    "status": "held",
                    "who_is_boss_now": BOSS,
                    "last_heartbeat": (T0 - timedelta(minutes=45)).isoformat(),
                    "claim_queue": [],
                    "as_of_history": [],
                }
            ),
            encoding="utf-8",
        )
        raw = path.read_bytes()
        rc = watchdog.main(["--claim-file", str(path), "--dry-run"])
        assert rc == 0
        assert path.read_bytes() == raw

    def test_main_fails_closed_on_a_corrupt_claim(self, watchdog, tmp_path):
        path = tmp_path / "claim.json"
        path.write_bytes(b"{ nope")
        raw = path.read_bytes()
        with pytest.raises(watchdog.seat_protocol.CorruptClaimFileError):
            watchdog.main(["--claim-file", str(path)])
        assert path.read_bytes() == raw


# ---------------------------------------------------------------------------
# CLI


class TestCli:
    def _run(self, seat_protocol, *args):
        return seat_protocol.main(list(args))

    def test_cli_round_trip(self, seat_protocol, tmp_path):
        claim = tmp_path / "claim.json"
        rc = self._run(
            seat_protocol, "join", "--agent", BOSS, "--claim-file", str(claim),
            "--now", "2026-10-13T12:00:00Z",
        )
        assert rc == 0
        record = json.loads(claim.read_text(encoding="utf-8"))
        assert record["who_is_boss_now"] == BOSS

    def test_cli_refusal_exit_code(self, seat_protocol, tmp_path):
        claim = tmp_path / "claim.json"
        self._run(
            seat_protocol, "join", "--agent", BOSS, "--claim-file", str(claim),
            "--now", "2026-10-13T12:00:00Z",
        )
        rc = self._run(
            seat_protocol, "renew", "--agent", C1, "--claim-file", str(claim),
            "--now", "2026-10-13T12:01:00Z",
        )
        assert rc == 1  # protocol refusal, not a crash

    def test_cli_corrupt_claim_exit_code(self, seat_protocol, tmp_path):
        claim = tmp_path / "claim.json"
        claim.write_bytes(b"{ broken")
        rc = self._run(
            seat_protocol, "status", "--claim-file", str(claim),
        )
        assert rc == 2  # corrupt claim, named reason, file untouched

    def test_cli_dry_run_writes_nothing(self, seat_protocol, tmp_path):
        claim = tmp_path / "claim.json"
        self._run(
            seat_protocol, "join", "--agent", BOSS, "--claim-file", str(claim),
            "--now", "2026-10-13T12:00:00Z",
        )
        raw = claim.read_bytes()
        rc = self._run(
            seat_protocol, "renew", "--agent", BOSS, "--claim-file", str(claim),
            "--now", "2026-10-13T12:10:00Z", "--dry-run",
        )
        assert rc == 0
        assert claim.read_bytes() == raw

    def test_cli_assignment_supplies_the_claim_path(self, seat_protocol, tmp_path, monkeypatch):
        assignment = tmp_path / "assignment.json"
        assignment.write_text(
            json.dumps(
                {
                    "boss_failover": {
                        "check_in": {"claim_file_path": "state/boss_claim.json"}
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = self._run(
            seat_protocol, "join", "--agent", BOSS, "--assignment", str(assignment),
            "--now", "2026-10-13T12:00:00Z",
        )
        assert rc == 0
        assert (tmp_path / "state" / "boss_claim.json").is_file()

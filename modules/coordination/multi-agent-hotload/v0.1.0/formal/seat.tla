---------------------------- MODULE seat ----------------------------
\* Formal model of the seat protocol (ROLES.md; scripts/seat_protocol.py).
\*
\* The runtime keeps one authoritative seat in a local claim record: a boss
\* lease, a FIFO claim queue, watchdog vacancy, zombie rejection, and
\* append-only as-of history. This module model-checks the safety of that
\* protocol:
\*
\*   AtMostOneBoss       - no state has two agents each holding a valid lease
\*   QueueFIFO           - the seat is served in claim-queue arrival order
\*   AppendOnly          - as_of_history only grows; past entries are kept
\*   NoAppointByWatchdog - expire vacates but never appoints
\*   NoZombieAction      - a past-TTL agent's boss-action is refused
\*   MonotonicTime       - no write records a time older than the newest
\*
\* Check with:  java -cp tla2tools.jar tlc2.TLC -config seat.cfg seat.tla
\************************************************************************
EXTENDS Naturals, Integers, Sequences, FiniteSets

CONSTANTS Agents, TimeMax, TTL

\* The clock domain, 0 .. TimeMax (a small interval; see seat.cfg). The clock
\* only moves forward, modelling advancing wall-clock time. Every write stamps
\* the current clock, so recorded times never run backwards -- the property
\* scripts/seat_protocol.py enforces by refusing a regressed ``now``.
Time == 0..TimeMax

\* The empty-seat / no-check-in sentinel. It is -1 (an integer outside every
\* Time value) rather than a string, so Time \cup {NoBoss} stays a set TLC can
\* test membership in directly -- TLC rejects a string checked against the
\* integer interval Time. It is distinct from every agent identity too, since
\* agents are the symbolic constants a1, a2, a3.
NoBoss == -1

VARIABLES boss, status, hb, queue, hist, now, arrival, last_action

vars == <<boss, status, hb, queue, hist, now, arrival, last_action>>

\* One as-of history entry: who held the seat, which operation recorded it,
\* when, and when that tenure ended (NoBoss while still open).
Entry == [boss_agent_id : Agents,
          by : {"join", "take-seat", "expire"},
          as_of : Time,
          ended_at : Time \cup {NoBoss}]

\* A boss action remembers the lease it was taken under, so the refusal rule
\* stays checkable after the clock has moved on (see NoZombieAction). The
\* deadline may exceed TimeMax (a lease taken at the last tick is valid past
\* it), so the domain is Nat, not Time.
ActionRec == [at : Time, deadline : Nat]

\* The no-action-yet sentinel. A record (rather than the numeric NoBoss) so
\* every comparison involving last_action stays between values of one shape --
\* TLC refuses to compare a record with a non-record.
NoAction == [at |-> -1, deadline |-> -1]

\* hb[a] is agent a's last check-in. ROLES.md: the seat is held only under a
\* valid lease, and a lease is valid while the check-in is within TTL. The
\* claim file stores a single last_heartbeat for the sitting boss; the model
\* keeps a check-in per agent because the safety claim is about agents' leases
\* (the single field is the holder's entry in this map).
LeaseValid(a) == IF hb[a] = NoBoss THEN FALSE ELSE now <= hb[a] + TTL

\* The sitting boss's check-in, and the derived lease state of the seat.
BossHb == IF boss = NoBoss THEN NoBoss ELSE hb[boss]
SeatHeld == IF BossHb = NoBoss THEN FALSE ELSE now <= BossHb + TTL
PastTTL == IF BossHb = NoBoss THEN FALSE ELSE now > BossHb + TTL

HeldBy(a) == boss = a /\ LeaseValid(a)

Queued == {queue[i] : i \in 1..Len(queue)}

TypeOK ==
    /\ boss \in Agents \cup {NoBoss}
    /\ status \in {"vacant", "occupied"}
    /\ hb \in [Agents -> Time \cup {NoBoss}]
    /\ queue \in Seq(Agents)
    /\ hist \in Seq(Entry)
    /\ now \in Time
    /\ arrival \in Seq(Agents)
    /\ last_action = NoAction \/ last_action \in ActionRec
    /\ (status = "occupied") <=> (boss /= NoBoss)

Init ==
    /\ boss = NoBoss
    /\ status = "vacant"
    /\ hb = [a \in Agents |-> NoBoss]
    /\ queue = <<>>
    /\ hist = <<>>
    /\ now = 0
    /\ arrival = <<>>
    /\ last_action = NoAction

Appoint(a, by) == [boss_agent_id |-> a, by |-> by, as_of |-> now, ended_at |-> NoBoss]
Vacate(a) == [boss_agent_id |-> a, by |-> "expire", as_of |-> now, ended_at |-> now]

\* The clock ticks; the seat is untouched.
Tick ==
    /\ now < TimeMax
    /\ now' = now + 1
    /\ UNCHANGED <<boss, status, hb, queue, hist, arrival, last_action>>

\* First continuer into an empty room takes the seat (ROLES.md fill order).
Join(a) ==
    /\ boss = NoBoss
    /\ queue = <<>>
    /\ boss' = a
    /\ status' = "occupied"
    /\ hb' = [hb EXCEPT ![a] = now]
    /\ hist' = Append(hist, Appoint(a, "join"))
    /\ UNCHANGED <<queue, arrival, last_action, now>>

\* The sitting boss renews its check-in. A zombie (past TTL) cannot renew.
Renew(a) ==
    /\ HeldBy(a)
    /\ hb' = [hb EXCEPT ![a] = now]
    /\ UNCHANGED <<boss, status, queue, hist, arrival, last_action, now>>

\* Append a claimant to the queue. Refused while the seat is held under a
\* valid lease; an agent already queued (or already boss) is never added twice.
Enqueue(a) ==
    /\ boss /= a
    /\ a \notin Queued
    /\ ~SeatHeld
    /\ queue' = Append(queue, a)
    /\ arrival' = Append(arrival, a)
    /\ UNCHANGED <<boss, status, hb, hist, last_action, now>>

\* The front of the queue takes the vacant seat. Appointment is an agent
\* operation; the watchdog never performs it (ROLES.md "Watchdog != failover").
TakeSeat(a) ==
    /\ boss = NoBoss
    /\ queue /= <<>>
    /\ queue[1] = a
    /\ queue' = Tail(queue)
    /\ boss' = a
    /\ status' = "occupied"
    /\ hb' = [hb EXCEPT ![a] = now]
    /\ hist' = Append(hist, Appoint(a, "take-seat"))
    /\ UNCHANGED <<arrival, last_action, now>>

\* The watchdog path: past TTL -> vacant. It vacates and appends history; it
\* never appoints and never reorders the queue.
Expire ==
    /\ PastTTL
    /\ boss' = NoBoss
    /\ status' = "vacant"
    /\ hist' = Append(hist, Vacate(boss))
    /\ UNCHANGED <<hb, queue, arrival, last_action, now>>

\* A woken old boss rejects boss-only actions and re-queues at the end.
ZombieReject(a) ==
    /\ boss /= a
    /\ a \notin Queued
    /\ queue' = Append(queue, a)
    /\ arrival' = Append(arrival, a)
    /\ UNCHANGED <<boss, status, hb, hist, last_action, now>>

\* Boss-only action (ACCEPT/REJECT, appointing). Permitted only for the holder
\* under a valid lease; a past-TTL agent is refused. Read-only, so it records
\* the lease it acted under rather than moving the seat. HeldBy(a) guarantees
\* hb[a] is a real check-in, so the deadline is hb[a] + TTL.
BossAction(a) ==
    /\ HeldBy(a)
    /\ last_action' = [at |-> now, deadline |-> hb[a] + TTL]
    /\ UNCHANGED <<boss, status, hb, queue, hist, arrival, now>>

Next ==
    \/ Tick
    \/ \E a \in Agents : Join(a)
    \/ \E a \in Agents : Renew(a)
    \/ \E a \in Agents : Enqueue(a)
    \/ \E a \in Agents : TakeSeat(a)
    \/ Expire
    \/ \E a \in Agents : ZombieReject(a)
    \/ \E a \in Agents : BossAction(a)

Spec == Init /\ [][Next]_vars

\* Safety 1: at most one agent holds a valid (unexpired) lease.
AtMostOneBoss == Cardinality({a \in Agents : LeaseValid(a)}) <= 1

\* Safety 2: the queue is exactly the not-yet-served tail of arrival order, so
\* the seat is served in enqueue order (FIFO).
QueueFIFO ==
    /\ Len(queue) <= Len(arrival)
    /\ queue = SubSeq(arrival, Len(arrival) - Len(queue) + 1, Len(arrival))

\* Safety 3: every history entry the watchdog writes closes a tenure
\* (ended_at set) -- expire never opens (appoints) one.
NoAppointByWatchdog ==
    \A i \in 1..Len(hist) : hist[i].by = "expire" => hist[i].ended_at /= NoBoss

\* Safety 4: the last boss action was taken under a valid lease.
NoZombieAction ==
    IF last_action = NoAction THEN TRUE ELSE last_action.at <= last_action.deadline

\* Safety 5: no recorded time is newer than the clock, and history times are
\* non-decreasing -- a write never records a time older than the newest already
\* recorded.
MonotonicTime ==
    /\ \A i \in 1..Len(hist) : hist[i].as_of <= now
    /\ \A a \in Agents : hb[a] = NoBoss \/ hb[a] <= now
    /\ \A i \in 1..(Len(hist) - 1) : hist[i].as_of <= hist[i + 1].as_of

\* Safety 6: as_of_history only grows -- every step either leaves it unchanged
\* or appends exactly one entry, so past entries are never rewritten or dropped.
AppendOnly == [][ hist' = hist \/ \E e \in Entry : hist' = Append(hist, e) ]_hist

=========================================================================

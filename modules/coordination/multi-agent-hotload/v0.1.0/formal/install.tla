---------------------------- MODULE install ----------------------------
\* Formal model of the hotload install state machine (SPEC.md sections 3-4).
\*
\* The installer classifies every target artifact and writes only when no
\* artifact is unresolved. This module model-checks the safety of that rule:
\*
\*   NoClobber  - an artifact we must refuse is never written
\*   FailClosed - any unresolved artifact blocks every write
\*   InTarget   - writes only ever touch the declared artifact set
\*   Idempotent - re-applying a clean plan writes nothing new
\*
\* Check with:  tlc -config install.cfg install.tla
\************************************************************************
EXTENDS Naturals, FiniteSets

CONSTANTS Artifacts, Mode

\* Mode selects what a clean apply writes: a normal run creates the absent
\* artifacts; a forced run additionally regenerates the ones we own. Neither
\* ever writes a refused artifact.
ModeSet == {"normal", "force"}

\* The classification of a target path, per SPEC.md section 4 Layer A.
Kinds == {"absent", "ours_unchanged", "ours_edited",
          "foreign_identical", "foreign_different", "not_regular"}

\* absent               -> create
\* ours_*               -> keep (a --force run regenerates them)
\* foreign_identical    -> adopt: byte-identical to what we would write
\* foreign_different    -> refuse
\* not_regular          -> refuse (symlink or directory)
Create == {"absent"}
Ours   == {"ours_unchanged", "ours_edited"}
Adopt  == {"foreign_identical"}
Refuse == {"foreign_different", "not_regular"}

VARIABLES kind, written

vars == <<kind, written>>

CreateSet == {a \in Artifacts : kind[a] \in Create}
OursSet   == {a \in Artifacts : kind[a] \in Ours}
RefuseSet == {a \in Artifacts : kind[a] \in Refuse}

\* What a clean apply is allowed to write in the current mode.
WriteSet == IF Mode = "normal" THEN CreateSet ELSE CreateSet \cup OursSet

TypeOK ==
    /\ Mode \in ModeSet
    /\ kind \in [Artifacts -> Kinds]
    /\ written \subseteq Artifacts

Init ==
    /\ Mode \in ModeSet
    /\ kind \in [Artifacts -> Kinds]
    /\ written = {}

Clean == \A a \in Artifacts : kind[a] \notin Refuse

\* Apply the plan: write the writable set. Deterministic, so a rerun of a
\* fully applied clean plan is a no-op (see Idempotent).
Apply ==
    /\ Clean
    /\ written' = written \cup WriteSet
    /\ UNCHANGED kind

\* Refuse: an unresolved artifact blocks the whole install (zero writes).
Refuse_ ==
    /\ ~Clean
    /\ UNCHANGED vars

Next == Apply \/ Refuse_

Spec == Init /\ [][Next]_vars

\* Safety 1: an artifact we must refuse is never written.
NoClobber == written \cap RefuseSet = {}

\* Safety 2: any unresolved artifact blocks every write.
FailClosed == RefuseSet /= {} => written = {}

\* Safety 3: writes only touch the declared artifact set.
InTarget == written \subseteq Artifacts

\* Idempotence: a clean state has written only what a clean plan writes, so
\* re-applying it adds nothing (written \cup WriteSet = WriteSet).
Idempotent == Clean => written \subseteq WriteSet

=========================================================================

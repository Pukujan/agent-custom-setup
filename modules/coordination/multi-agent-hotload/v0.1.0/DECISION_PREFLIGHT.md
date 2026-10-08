# ACS decision preflight — optional bridge to PCM

**Status:** opt-in adapter. This is not yet part of the certified stack and does not alter the installer, boss election or release train.  
**Owning issues:** [ACS #85](https://github.com/Pukujan/agent-custom-setup/issues/85), [PCM #241](https://github.com/Pukujan/project-continuity-modules/issues/241).  
**Underlying PCM protocol:** [Decision preflight](https://github.com/Pukujan/project-continuity-modules/blob/task/PCM-0070-decision-preflight/docs/DECISION_PREFLIGHT.md) (currently a task branch, subject to merge).

## Why

A valid lease means an agent can coordinate a task. It does **not** mean the task's purpose, accepted decision or underlying issue state is still valid. PCM already owns issue authority and continuity; ACS must not maintain another belief store. This small adapter delegates a **live read-only freshness check** to PCM at the moment of a consequential task.

## How to use (only after PCM module is available)

Place a scoped, reviewed PCM decision-precondition JSON beside the task's working artifacts. Do not auto-refresh it from the latest issue; first review material corrections and record the amended decision on the owning issue.

From the hotload module's scripts directory:

~~~bash
python decision_preflight.py \
  --expect /path/to/reviewed-task-precondition.json \
  --task ACS-0015 \
  --repo Pukujan/agent-custom-setup
~~~

Results:
- CURRENT / exit 0: only the issue and referenced decision **revision** agree; verify role/lease, current GitHub issue scope, owner direction and other gates independently.
- STALE or REVIEW_REQUIRED / exit 2: halt the affected consequential action, inspect source changes, re-plan if appropriate and explicitly refresh the reviewed precondition.
- UNKNOWN / exit 3: PCM module unavailable, API failure, malformed data, task binding mismatch or unverifiable source. Fail closed for guarded action.

The adapter itself performs no network calls or writes; the invoked PCM module makes GitHub GETs and returns the result. If the certified PCM checkout lacks the new module, the script returns UNKNOWN. Do **not** bypass it or mark CURRENT; do not flip the stack pin until the PCM change has been reviewed, merged and certified.

## Activation policy

Only tasks with an explicit decision precondition opt into this check. Run at admission/resume **and immediately before expensive, high-impact or irreversible actions**; do not run at every trivial shell read. Pending the certified PCM release this is **not** a required part of existing ACS hotload installations. Keep the independent ACS coordination protocol unchanged. No new service, database, secret, or background polling agent.

This is a conditional integration, not a claim that the pack automatically blocks all stale decisions. That stronger integration requires actual claim/action-hook wiring, a certified dependency, and evidence that it does not break the protected task lifecycle.

## Separate responsibilities

| Layer | Owns |
| --- | --- |
| OIO | Observational issue intake, filer/authorization provenance |
| PCM | Canonical issue state reconciliation and evidence/history semantics |
| ACS | Whether the assigned agent holds the correct seat/lease and may execute a task |
| Product/experience owner | Whether the plan and product outcome are actually correct and accepted |

Matching current state does not imply that a marketed story is persuasive, a product design is valid, or an agent is authorized to write. Every layer retains its own acceptance.

## Layered verification requirements

The current adapter tests establish only the optional command boundary: matching task/revision allows the explicitly guarded next action; stale, changed, or unknown results block it. A [PCM+ACS verification protocol](https://github.com/Pukujan/project-continuity-modules/blob/task/PCM-0070-decision-preflight/docs/plans/DECISION_FRESHNESS_VERIFICATION.md) separately requires a *real* GitHub issue transition, blind agent-resumption trials, and finally an actual enforcement hook on consequential ACS actions before system-wide effectiveness can be claimed. Neither the existing lease checks nor the present optional adapter guarantees that all workers invoke this preflight. Do not confuse a green test suite with that stronger safety property.

## Verification and limits

Run the new test module with the pack suite:

~~~bash
python -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests/test_decision_preflight.py -q
~~~

The tests use offline mocks. They test correct delegation, status codes, unavailability, unexpected response and task/repository binding. They do not run an actual task or check production GitHub private permissions. The PCM test suite separately exercises comparison and API-failure behavior.

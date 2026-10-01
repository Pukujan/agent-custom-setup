# JEV OSS compare decision (Refs #25)

ACS gates stay the HOTLOAD default for Claude and Kilo. We added an optional
comparison lane (`jev-oss-compare`) so auto-mode hard-deny patterns and a
jev-gate-shaped post-run stub can be scored on the same packs without replacing
live PreToolUse.

See module README decision table and `reports/jev-oss-compare.html`.

#!/usr/bin/env bash
# HLD-0001 seeded verification — the discriminating criteria, for real.
#
# Runs the *pinned* OIO installer and the *real* acs_install.py on Linux (WSL
# or a container) against scratch adopters, and checks the three criteria that
# decide the holdout:
#
#   C1  a foreign AGENTS.md is merged inside a delimited region; the user's
#       text stays byte-identical
#   C2  a hand-edited managed region is refused, never clobbered
#   C3  a missing .content-system adapter fails closed and writes nothing
#
# This is NOT the blind holdout run (that needs a cold agent and a seeded CGM
# adapter). It is the reproducible check that the behaviour those criteria
# measure actually holds end-to-end, against the real components.
#
# Usage:
#   OIO_SRC=/path/to/observational-issue-ops \
#   ACS_ROOT=/path/to/agent-custom-setup \
#   bash HLD-0001-verify.sh
set -u
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

OIO_SRC=${OIO_SRC:-/mnt/d/development/observational-issue-ops}
ACS_ROOT=${ACS_ROOT:-/mnt/d/development/acs-work}
PACK=${PACK:-$ACS_ROOT/modules/coordination/multi-agent-hotload/v0.1.0}

OIO_SHA=$(python3 - "$ACS_ROOT/stack-mesh.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["requires"]["observational-issue-ops"]["commit"])
PY
)
echo "mesh OIO commit: $OIO_SHA"

git clone -q --local --no-hardlinks "$OIO_SRC" "$WORK/oio"
git -C "$WORK/oio" checkout -q "$OIO_SHA"
INST="$WORK/oio/.github/scripts/oio_installer.py"
head=$(git -C "$WORK/oio" rev-parse HEAD)
[ "$head" = "$OIO_SHA" ] || { echo "FAIL: OIO checkout is $head, want $OIO_SHA"; exit 1; }

mkadopter() {  # $1=name -> git repo with a user-owned AGENTS.md, no OIO marker
  local d="$WORK/$1"
  mkdir -p "$d"; git -C "$d" init -q
  git -C "$d" config user.email t@t.invalid; git -C "$d" config user.name t
  printf '%s\n' '# My Repo' '' 'My own instructions, do not touch.' > "$d/AGENTS.md"
  echo keepme > "$d/f.txt"
  git -C "$d" add -A; git -C "$d" commit -qm init
}

fail=0

echo
echo "===== C1: foreign AGENTS.md, no OIO marker -> merge inside a delimited region ====="
mkadopter c1
cp "$WORK/c1/AGENTS.md" "$WORK/c1.before"
python3 "$INST" --target "$WORK/c1" --project-id example/c1 > "$WORK/c1.log" 2>&1
rc=$?
[ "$rc" = 0 ] && echo "C1 install rc=0" || { echo "C1 install rc=$rc (want 0)"; fail=1; }
python3 - "$WORK/c1/AGENTS.md" "$WORK/c1.before" <<'PY' || fail=1
import re, sys, pathlib
after = pathlib.Path(sys.argv[1]).read_text()
before = pathlib.Path(sys.argv[2]).read_text()
assert "<!-- oio:issue-log-guidance:start -->" in after, "OIO region not inserted"
assert "<!-- oio:issue-log-guidance:end -->" in after, "OIO region not closed"
stripped = re.sub(r"\n?<!-- oio:issue-log-guidance:start -->.*?<!-- oio:issue-log-guidance:end -->\n?",
                  "", after, flags=re.S)
assert stripped == before, f"user text changed:\n before={before!r}\n after ={stripped!r}"
print("C1 user text byte-identical outside the region: YES")
PY

echo
echo "===== C2: hand-edited managed region -> refuse, do not clobber ====="
python3 - "$WORK/c1/AGENTS.md" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text()
p.write_text(t.replace("Confirm the exact destination", "Confirm the exact destination (HAND-EDITED)"))
PY
cp "$WORK/c1/AGENTS.md" "$WORK/c2.before"
python3 "$INST" --target "$WORK/c1" --project-id example/c1 > "$WORK/c2.log" 2>&1
rc=$?
if [ "$rc" != 0 ]; then echo "C2 reinstall rc=$rc (refused)"; else echo "C2 reinstall rc=0 (want non-zero)"; fail=1; fi
if cmp -s "$WORK/c1/AGENTS.md" "$WORK/c2.before"; then echo "C2 hand-edited region NOT clobbered: YES"; else echo "C2 region was clobbered"; fail=1; fi
grep -iq "edited" "$WORK/c2.log" || { echo "C2 report did not name the edit"; fail=1; }

echo
echo "===== C3: no .content-system adapter -> fail closed, write nothing ====="
mkadopter c3
python3 "$PACK/scripts/acs_install.py" --acs-root "$ACS_ROOT" \
  --adopter-root "$WORK/c3" --pcm-root "$WORK/pcm" --cgm-root "$WORK/cgm" \
  --oio-root "$WORK/oio" > "$WORK/c3.log" 2>&1
rc=$?
if [ "$rc" != 0 ]; then echo "C3 rc=$rc (fail closed)"; else echo "C3 rc=0 (want non-zero)"; fail=1; fi
grep -q "content-system" "$WORK/c3.log" || { echo "C3 report did not name .content-system"; fail=1; }
if [ -e "$WORK/c3/.coord" ] || [ -e "$WORK/c3/stack-manifest.json" ]; then
  echo "C3 wrote files despite failure"; fail=1
else
  echo "C3 wrote nothing: YES"
fi

echo
if [ "$fail" = 0 ]; then echo "HLD-0001 seeded verification: PASS (C1, C2, C3)"; else echo "HLD-0001 seeded verification: FAIL"; fi
exit "$fail"

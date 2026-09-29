#!/usr/bin/env python3
"""storm-report.py — read-only loop-diagnostics for omp sessions (ACS-0005 ops layer).

Scans omp session artifacts and prints per-session delivery/loop metrics, so
"is the advisory storm back?" and "which channel caused it?" are answered from
durable data instead of re-litigating a transcript by hand. The #35 forensics
(94 advisor notes, ~11 native cards, 83 court injections, async-result replays)
reproduce with:

    python3 oh-my-pi/ops/storm-report.py ~/.omp/agent/sessions --limit 10
    python3 oh-my-pi/ops/storm-report.py <one-session.jsonl>

Data sources are append-only on-disk session files; nothing requires the
extensions to be enabled. jev-court v2 and loop-guard add structured records
(`com.jev-court.decision` with an `outcome` field; `com.acs.loopguard.state`
{replayIncidents, echoIncidents, reason, ts}) so outcomes are read, not
inferred; v1 sessions lack them and are still measurable from message content.
Redelivered background results are `custom_message` entries with customType
"async-result" naming job ids in the body ("Background job <Id> has completed"
/ "── Job <Id>"). Replay identity is PER JOB (an entry counts as a replay when
every job it carries was already announced by an earlier entry): #35 interleaves
singles and batches (Recipe, Guardian, Recipe+Guardian, …), so whole-set
signatures mask re-arrivals — same rule the extension marks with.

Exit 0 always (diagnostic, not a gate); --fail-on-warn exits 1 if any WARN.
"""

import argparse
import glob
import json
import os
import re
import sys

STOP_RE = re.compile(r"^\s*(stop|halt|cancel|enough|quit|pause)\b", re.I)
JOB_ID_RE = re.compile(r"(?:Background job|── Job) ([A-Za-z0-9_-]+)")

# Proposed thresholds (untested against a fleet): tuned to the #35 session, where
# healthy native-channel behaviour was ~11 accepted notes and the loop was 83
# injections + 3 fully-redundant replays + post-stop pressure. See issue #37.
WARN_VERDICTS = 15       # injected court verdicts in one session
WARN_NOTES = 60          # advisor advise() calls produced
WARN_NATIVE = 30         # native <advisory> renders
WARN_REPLAYS = 1         # fully-redundant async-result announcements
WARN_DECISION_RATIO = 0.5  # decided notes that got injected


def norm(s):
    s = (s or "").lower().replace("\u00a0", " ")
    s = "".join(c if (c.isalnum() or c == " ") else " " for c in s)
    return re.sub(r"\s+", " ", s).strip()


def blocks_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(str(b.get("text", "")))
    return "\n".join(out)


def parse(line):
    try:
        v = json.loads(line)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _ts(v):
    for k in ("timestamp", "ts"):
        if isinstance(v.get(k), (int, float)):
            return float(v[k])
    return 0.0


def scan_session(path):
    m = {
        "session": os.path.basename(path),
        "verdict_injections": 0,
        "decision_records": {},          # outcome -> count (jev-court v2)
        "loopguard_records": [],         # reason list (loop-guard)
        "advisory_native": 0,
        "advisor_notes": 0,
        "advisor_notes_unique": 0,
        "async_announcements": 0,
        "async_replays": 0,
        "owner_stops": 0,
        "post_stop_verdicts": 0,
        "size_bytes": 0,
        "error": None,
    }
    if not os.path.isfile(path):
        m["error"] = "missing primary session file"
        return m

    m["size_bytes"] = os.path.getsize(path)
    note_keys = set()
    announced_jobs = set()
    last_stop_ts = 0.0

    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            v = parse(line)
            if not v:
                continue
            if v.get("type") == "custom_message" and v.get("customType") == "com.jev-court.verdict":
                m["verdict_injections"] += 1
                ts = _ts(v)
                if last_stop_ts and ts and ts >= last_stop_ts:
                    m["post_stop_verdicts"] += 1
            if v.get("type") == "custom_message":
                ct = v.get("customType")
                content_str = blocks_text(v.get("content"))
                if ct == "com.jev-court.decision":
                    d = v.get("data") or {}
                    o = str(d.get("outcome", "unknown"))
                    m["decision_records"][o] = m["decision_records"].get(o, 0) + 1
                elif ct == "com.acs.loopguard.state":
                    d = v.get("data") or {}
                    m["loopguard_records"].append(str(d.get("reason", "unknown")))
                elif ct == "async-result":
                    jobs = set(JOB_ID_RE.findall(content_str))
                    if jobs:
                        m["async_announcements"] += 1
                        if jobs <= announced_jobs:
                            m["async_replays"] += 1
                        announced_jobs |= jobs
                if "<advisory" in content_str:
                    m["advisory_native"] += 1
            msg = v.get("message") or {}
            if msg.get("role") == "user":
                txt = blocks_text(msg.get("content")).strip()
                if STOP_RE.match(txt) and len(txt) < 40:
                    m["owner_stops"] += 1
                    last_stop_ts = _ts(v)

    # Advisor note counts from the artifacts dir owned by this session file.
    art = path[: -len(".jsonl")] if path.endswith(".jsonl") else path
    if os.path.isdir(art):
        for af in glob.glob(os.path.join(art, "__advisor*.jsonl")):
            with open(af, "r", errors="ignore") as fh:
                for line in fh:
                    if '"advise"' not in line:
                        continue
                    v = parse(line)
                    msg = (v or {}).get("message") or {}
                    if msg.get("role") != "assistant":
                        continue
                    cont = msg.get("content")
                    if not isinstance(cont, list):
                        continue
                    for b in cont:
                        if not (isinstance(b, dict) and b.get("name") == "advise"):
                            continue
                        args = b.get("arguments") or b.get("input") or {}
                        note = args.get("note")
                        if note:
                            m["advisor_notes"] += 1
                            note_keys.add(
                                f"{os.path.basename(af)}::{norm(str(note))[:240]}"
                            )
        m["advisor_notes_unique"] = len(note_keys)

    decided = sum(m["decision_records"].values())
    m["decision_total"] = decided
    m["decision_ratio"] = (
        round(m["verdict_injections"] / decided, 3) if decided else None
    )
    m["warnings"] = _warnings(m)
    return m


def _warnings(m):
    w = []
    if m["verdict_injections"] > WARN_VERDICTS:
        w.append(
            f"verdict injections {m['verdict_injections']} > {WARN_VERDICTS} — court delivering (v1 symptom; check enabled + budgets)"
        )
    if m["advisor_notes"] > WARN_NOTES:
        w.append(
            f"advisor notes {m['advisor_notes']} > {WARN_NOTES} — roster too noisy (see #35: 94 notes)"
        )
    if m["advisory_native"] > WARN_NATIVE:
        w.append(f"native advisories {m['advisory_native']} > {WARN_NATIVE}")
    if m["async_replays"] > WARN_REPLAYS:
        w.append(
            f"async-result replays {m['async_replays']} > {WARN_REPLAYS} — fully-redundant background deliveries (issue #35 symptom 1)"
        )
    if m["post_stop_verdicts"] > 0:
        w.append(
            f"{m['post_stop_verdicts']} verdict(s) after an owner stop — stop-suppression gap"
        )
    r = m["decision_ratio"]
    if r is not None and r > WARN_DECISION_RATIO:
        w.append(
            f"decision->injection ratio {r} > {WARN_DECISION_RATIO} — most adjudicated notes still reaching primary"
        )
    if m["loopguard_records"].count("task_echo_incident") >= 2:
        w.append(">=2 subagent tool-echo incidents — delegation failing (issue #35 symptom 2)")
    if "replay_incident" in m["loopguard_records"]:
        w.append("loop-guard recorded replay incident(s) — dedup marking active (informational)")
    return w


def find_sessions(root):
    """Discover primary session JSONL files under an omp sessions root."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".jsonl") and "__advisor" not in f:
                full = os.path.join(dirpath, f)
                art = full[: -len(".jsonl")]
                # primary sessions sit at project level (dir starts with "-")
                # and/or own an artifacts dir; subagent transcripts live inside.
                if os.path.basename(dirpath).startswith("-") or os.path.isdir(art):
                    out.append(full)
        dirnames[:] = [d for d in dirnames if not d.startswith("__")]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "target",
        help="omp sessions root (e.g. ~/.omp/agent/sessions), one <session>.jsonl, or an artifacts dir",
    )
    ap.add_argument("--project", help="restrict to one project subdir name")
    ap.add_argument("--limit", type=int, default=20, help="most recent N sessions")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--fail-on-warn", action="store_true", help="exit 1 if any WARN")
    a = ap.parse_args()

    t = os.path.abspath(os.path.expanduser(a.target))
    if os.path.isfile(t) and t.endswith(".jsonl"):
        sess = [t]
    elif os.path.isdir(t):
        root = os.path.join(t, a.project) if a.project else t
        sess = find_sessions(root)
    else:
        print(f"not found: {t}", file=sys.stderr)
        return 2

    sess.sort(key=os.path.getmtime, reverse=True)
    sess = sess[: a.limit]
    rows = [scan_session(p) for p in sess]

    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        print(f"sessions scanned: {len(rows)}  (thresholds proposed, see #37)\n")
        for r in rows:
            flag = "WARN" if r["warnings"] else "  ok"
            print(f"{flag}  {r['session'][:52]:<52}  {r['size_bytes'] / 1e6:6.1f}MB")
            print(
                f"       notes {r['advisor_notes']:>4} (uniq {r['advisor_notes_unique']:>4})"
                f" | verdicts {r['verdict_injections']:>4}"
                f" | native {r['advisory_native']:>3}"
                f" | decisions {r['decision_total']:>4}"
                f" | announcements {r['async_announcements']:>2} (replays {r['async_replays']:>2})"
                f" | stops {r['owner_stops']}"
                f"{'' if not r['post_stop_verdicts'] else ' (post-stop verdicts: ' + str(r['post_stop_verdicts']) + ')'}"
            )
            if r["decision_records"]:
                top = sorted(r["decision_records"].items(), key=lambda x: -x[1])[:4]
                print(f"       outcomes: {dict(top)}")
            if r["loopguard_records"]:
                lg = {}
                for x in r["loopguard_records"]:
                    lg[x] = lg.get(x, 0) + 1
                print(f"       loopguard: {lg}")
            for w in r["warnings"]:
                print(f"       ! {w}")
            print()

    if a.fail_on_warn and any(r["warnings"] for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

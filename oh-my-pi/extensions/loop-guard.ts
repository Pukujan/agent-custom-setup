/**
 * loop-guard — delivery-hygiene extension for #35 (harness-side mechanisms).
 *
 * Complements jev-court (advisor adjudication) by handling the two injection
 * channels jev-court does not own:
 *
 * 1. REDELIVERED BACKGROUND RESULTS (#35 symptom 1). TRUE shape, verified
 *    against the #35 session JSONL: redelivered async jobs are persisted as
 *    `custom_message` entries with customType "async-result" whose body names
 *    job ids ("Background job <Id> has completed…" / "── Job <Id> …"). The
 *    same job id can re-appear later with a DIFFERENT body, so replay identity
 *    keys on the job-id SET, not on text. The `context` handler fires per
 *    provider request over the persisted message list, therefore marking is
 *    STATELESS and deterministic: within one request, entries whose job-id set
 *    repeats are ranked by (timestamp, request position) — the earliest
 *    occurrence is the original delivery (verbatim); every later occurrence is
 *    marked in-place as an already-consumed replay needing no acknowledgement
 *    turn. (The real #35 transcript interleaves other jobs between
 *    redeliveries — e.g. A@19:01, A+B@19:03, A@20:39 — so "first-in-list" is
 *    wrong; timestamp rank is correct.) Re-firing re-derives the identical
 *    output: nothing stacks, nothing double-counts. Entries are never removed;
 *    assistant/toolResult pairing and provider integrity stay intact. The WAKE
 *    itself is harness-owned (upstream residue, #37); this removes only the
 *    re-audit pressure from the content.
 *
 * 2. NO-OP SUBAGENT ECHOES (#35 symptom 2): task-role subagents that return a
 *    verbatim echo of their own tool-call JSON burned ~13 min of parent audit
 *    turns. On `tool_result` (toolName "task"), an echo-shaped result gets a
 *    passive `additionalContext` naming the failure and the two allowed next
 *    moves (implement directly | re-spawn once). Content and isError are NOT
 *    mutated — guidance rides outside the tool output, the documented-safe
 *    path.
 *
 * Both handlers are observation/marking only: no blocks, no sends, no wakes,
 * no steering. Ops capture: one compact `com.acs.loopguard.state` entry per
 * incident (via appendEntry — invisible to the model, durable in the session
 * JSONL, read by oh-my-pi/ops/storm-report.py for long-run forensics).
 * `/loopguard` shows live counters.
 */

import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";

type TextBlock = { type: string; text?: string };

// One of the host's content shapes: blocks of {type,text}. Non-arrays are
// handled by the string branch at the call site — we only patch text we
// positively recognizes.
function textBlocks(content: unknown): TextBlock[] | undefined {
  if (!Array.isArray(content)) return undefined;
  return content as TextBlock[];
}

function blocksText(blocks: TextBlock[] | undefined): string {
  if (!blocks) return "";
  return blocks
    .filter((b) => b && b.type === "text" && typeof b.text === "string")
    .map((b) => b.text as string)
    .join("\n");
}

const JOB_ID_RE = /(?:Background job|── Job) ([A-Za-z0-9_-]+)/g;

const MARK_PREFIX =
  "[loop-guard] REPLAY of already-consumed background job result(s) — these jobs were delivered earlier in the session; continue the primary task, no acknowledgement turn required.\n";

export default function (pi: ExtensionAPI) {
  pi.setLabel("Loop Guard — replay marking + subagent echo detection");

  // Counters are incident-based per session; marking itself is stateless.
  let replayIncidents = 0; // distinct job-sets observed as redelivered
  let echoIncidents = 0;
  const countedIncidents = new Set<string>(); // sigs already counted here

  // Ops capture: one compact record per incident — exactly what
  // oh-my-pi/ops/storm-report.py aggregates offline for long-run debugging.
  function persistState(reason: string) {
    try {
      pi.appendEntry("com.acs.loopguard.state", {
        replayIncidents,
        echoIncidents,
        reason,
        ts: Date.now(),
      });
    } catch {
      /* before runtime init: memory-only */
    }
  }

  // ---------- 1) context: mark repeated async-result entries ----------

  pi.on(
    "context",
    (event: { messages?: unknown }, ctx: ExtensionContext) => {
      const msgs = Array.isArray(event?.messages) ? event.messages : undefined;
      if (!msgs) return;

      // Pass 1: collect async-result entries with request position + timestamp.
      type Hit = { m: Record<string, unknown>; sig: string; idx: number; ts: number };
      const hits: Hit[] = [];
      let idx = 0;
      for (const raw of msgs) {
        idx++;
        if (!raw || typeof raw !== "object") continue;
        const m = raw as Record<string, unknown>;
        if (m.role !== "custom" || m.customType !== "async-result") continue;
        // Custom entries persist content as a bare string or text blocks.
        const text =
          typeof m.content === "string"
            ? m.content
            : blocksText(textBlocks(m.content));
        const ids = [...text.matchAll(JOB_ID_RE)].map((x) => x[1]);
        if (!ids.length) continue;
        hits.push({
          m,
          sig: [...new Set(ids)].sort().join("+"),
          idx,
          ts: Number(m.timestamp ?? m.ts ?? 0),
        });
      }
      if (!hits.length) return;

      // Pass 2: rank per sig by (ts, idx); earliest stays verbatim, rest mark.
      const rank = new Map<string, Hit[]>();
      for (const h of hits) {
        const arr = rank.get(h.sig) ?? [];
        arr.push(h);
        rank.set(h.sig, arr);
      }
      let changed = false;
      const newIncidents: string[] = [];
      const out = msgs.map((raw) => {
        const hit = hits.find((h) => h.m === raw);
        if (!hit) return raw;
        const group = rank.get(hit.sig)!;
        const first = group.reduce((a, b) =>
          b.ts !== a.ts ? (b.ts < a.ts ? b : a) : b.idx < a.idx ? b : a,
        );
        if (hit === first) return raw;
        changed = true;
        if (!countedIncidents.has(hit.sig)) {
          countedIncidents.add(hit.sig);
          newIncidents.push(hit.sig);
        }
        return markEntry(hit.m);
      });
      if (!changed) return;
      if (newIncidents.length) {
        replayIncidents += newIncidents.length;
        persistState("replay_incident");
      }
      ctx.ui?.setStatus?.("loop-guard", `replay-incidents=${replayIncidents}`);
      return { messages: out };
    },
  );

  // In-place marking only: never removes entries. Idempotent — an already
  // marked entry returns untouched so a re-fire can never stack prefixes.
  function markEntry(m: Record<string, unknown>): Record<string, unknown> {
    const bare = MARK_PREFIX.trim();
    if (typeof m.content === "string")
      return m.content.startsWith(bare) ? m : { ...m, content: MARK_PREFIX + m.content };
    const blocks = textBlocks(m.content);
    if (blocks && blocks.length) {
      if (blocks.some((b) => b.type === "text" && (b.text ?? "").startsWith(bare)))
        return m;
      const marked = blocks.map((b) =>
        b.type === "text" && typeof b.text === "string"
          ? { ...b, text: MARK_PREFIX + b.text }
          : b,
      );
      return { ...m, content: marked };
    }
    return m;
  }

  // ---------- 2) tool_result: flag task-role echo results ----------

  pi.on(
    "tool_result",
    (event: {
      toolName?: string;
      isError?: boolean;
      content?: unknown;
    }) => {
      if (event?.toolName !== "task" || event.isError) return;
      const text =
        typeof event.content === "string"
          ? event.content
          : blocksText(textBlocks(event.content));
      if (!looksLikeToolEcho(text)) return;
      echoIncidents++;
      persistState("task_echo_incident");
      // Passive guidance only: content/details/isError NOT mutated.
      return {
        additionalContext:
          "[loop-guard] This task result appears to be a verbatim echo of the subagent's own tool-call JSON — no deliverable was produced. Do not spend an audit turn on it: implement the unit directly, or re-spawn the subagent ONCE with the missing output named. A second echo means delegation is wrong for this unit.",
      };
    },
  );

  pi.on("session_start", (_e, ctx: ExtensionContext) => {
    // Rebuild counters from the newest persisted record (observability
    // continuity across restarts). Marking needs no state: it is re-derived
    // from (ts, position) rank in every request.
    try {
      const sm = ctx.sessionManager as unknown as {
        getBranch?: () => Array<Record<string, unknown>>;
      };
      if (typeof sm.getBranch === "function") {
        let latest: Record<string, unknown> | undefined;
        for (const e of sm.getBranch())
          if (e.type === "custom" && e.customType === "com.acs.loopguard.state")
            latest = e.data as Record<string, unknown>;
        if (latest) {
          replayIncidents = Number(latest.replayIncidents) || 0;
          echoIncidents = Number(latest.echoIncidents) || 0;
        }
      }
    } catch {
      /* fresh session: counters start at zero */
    }
  });

  pi.registerCommand("loopguard", {
    description: "Loop-guard status: replay incidents marked, task echoes flagged",
    handler: async (_args, ctx: ExtensionContext) => {
      ctx.ui.notify(
        `loop-guard · replay incidents=${replayIncidents} · task echo incidents=${echoIncidents} · full history: python3 oh-my-pi/ops/storm-report.py <sessions>`,
        "info",
      );
    },
  });
}

/**
 * Echo heuristic: the result body parses as JSON (or is JSON-shaped text) that
 * carries tool-call structure and essentially no prose. Deliberately narrow —
 * false positives cost a guidance line, false negatives fall back to today's
 * behavior.
 */
function looksLikeToolEcho(text: string): boolean {
  const t = text.trim();
  if (t.length < 40) return false;
  if (!(t.startsWith("{") || t.startsWith("["))) return false;
  const hasCallShape =
    /"type"\s*:\s*"(toolCall|tool_use|toolUse)"/.test(t) ||
    (/"name"\s*:/.test(t) && /"(arguments|input)"\s*:/.test(t));
  if (!hasCallShape) return false;
  try {
    JSON.parse(t);
    return true;
  } catch {
    // Truncated JSON echo still counts if prose ratio is negligible.
    const prose = t.replace(/\{[\s\S]*\}|\[[\s\S]*\]/g, "").trim().length;
    return prose < 20;
  }
}

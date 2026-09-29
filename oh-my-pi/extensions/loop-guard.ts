/**
 * loop-guard — delivery-hygiene extension for #35 (harness-side mechanisms).
 *
 * Complements jev-court (advisor adjudication) by handling the two injection
 * channels jev-court does not own:
 *
 * 1. REDDELIVERED BACKGROUND RESULTS (#35 symptom 1): async-job announcements
 *    re-enter the transcript as synthetic agent-attributed user messages
 *    ("### Session update ... [async-result] <Job>") — the #35 session repeated
 *    one such batch 4 times. On the `context` handler (pre-provider message
 *    list) a repeated announcement is MARKED as a replay in-place — never
 *    removed, so assistant/toolResult pairing and provider integrity stay
 *    intact. Marked text tells the primary explicitly: already consumed, no
 *    acknowledgement turn needed.
 *    Caveat (documented, not assumed): if the host excludes hidden agent-
 *    attributed companions from `context` inputs, the handler matches nothing
 *    and simply stays inert; it cannot make the wake fire or fail.
 *
 * 2. NO-OP SUBAGENT ECHOES (#35 symptom 2): task-role subagents that return a
 *    verbatim echo of their own tool-call JSON burned ~13 min of parent audit
 *    turns. On `tool_result` (toolName "task"), an echo-shaped result gets a
 *    passive `additionalContext` naming the failure and the two allowed next
 *    moves (implement directly | re-spawn once). Content and isError are NOT
 *    mutated — no fake failures, no transcript rewrites; guidance rides
 *    outside the tool output, which is the documented-safe mutation path.
 *
 * Both handlers are observation/marking only: no blocks, no sends, no wakes,
 * no steering. State is in-memory per process; counts surface via /loopguard.
 */

import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";

type TextBlock = { type: string; text?: string };

function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKC")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// A content array is the host's shape: blocks of {type,text}. Non-arrays are
// ignored — we only ever patch text blocks we positively recognize.
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

const ANNOUNCE_MARK =
  "[loop-guard] REPLAY of an earlier async-result announcement — the findings were already consumed; continue the primary task, no acknowledgement turn required.";

export default function (pi: ExtensionAPI) {
  pi.setLabel("Loop Guard — replay marking + subagent echo detection");

  const seenAnnouncements = new Map<string, number>(); // sig -> first-seen ts
  let replaysMarked = 0;
  let echoesFlagged = 0;

  // ---------- 1) context: mark repeated async-result announcements ----------

  pi.on(
    "context",
    (event: { messages?: unknown }, ctx: ExtensionContext) => {
      const msgs = Array.isArray(event?.messages) ? event.messages : undefined;
      if (!msgs) return;
      const now = Date.now();
      let changed = false;
      const out = msgs.map((raw) => {
        if (!raw || typeof raw !== "object") return raw;
        const m = raw as Record<string, unknown>;
        if (m.role !== "user") return raw;
        const blocks = textBlocks(m.content);
        const text = blocksText(blocks);
        // Only the documented announcement shape; unrelated user text untouched.
        if (!text.includes("[async-result]") && !text.includes("### Session update"))
          return raw;
        const sig = normalize(text).slice(0, 300);
        if (sig.length < 40) return raw;
        const prior = seenAnnouncements.get(sig);
        if (prior !== undefined) {
          if (blocks && blocks.length) {
            changed = true;
            replaysMarked++;
            const marked = blocks.map((b) =>
              b.type === "text" && typeof b.text === "string"
                ? { ...b, text: `${ANNOUNCE_MARK}\n\n${b.text}` }
                : b,
            );
            return { ...m, content: marked };
          }
          return raw;
        }
        seenAnnouncements.set(sig, now);
        return raw;
      });
      if (!changed) return;
      ctx.ui?.setStatus?.("loop-guard", `replay-marked=${replaysMarked}`);
      return { messages: out };
    },
  );

  // ---------- 2) tool_result: flag task-role echo results ----------

  pi.on(
    "tool_result",
    (event: {
      toolName?: string;
      isError?: boolean;
      content?: unknown;
    }) => {
      if (event?.toolName !== "task" || event.isError) return;
      const text = blocksText(textBlocks(event.content));
      if (!looksLikeToolEcho(text)) return;
      echoesFlagged++;
      // Passive guidance only: content/details/isError NOT mutated.
      return {
        additionalContext:
          "[loop-guard] This task result appears to be a verbatim echo of the subagent's own tool-call JSON — no deliverable was produced. Do not spend an audit turn on it: implement the unit directly, or re-spawn the subagent ONCE with the missing output named. A second echo means delegation is wrong for this unit.",
      };
    },
  );

  pi.registerCommand("loopguard", {
    description: "Loop-guard status: replays marked, echoes flagged",
    handler: async (_args, ctx: ExtensionContext) => {
      ctx.ui.notify(
        `loop-guard · announcements tracked=${seenAnnouncements.size} · replays marked=${replaysMarked} · task echoes flagged=${echoesFlagged}`,
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

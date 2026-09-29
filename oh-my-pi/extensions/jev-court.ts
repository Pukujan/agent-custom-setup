/**
 * jev-court — advisor adjudication pipeline (v2, hardened against #35).
 *
 * v1 defect set (issue #35, measured on the 2026-09-29 vastai-gpu-broker session):
 *   94 advisor notes -> harness native channel delivered ~11 (emission guard did its
 *   job); jev-court injected 83 messages, bypassing maxNotesPerUpdate/immuneTurns/
 *   stop-suppression, waking idle sessions (`aside` starts a turn when idle), and
 *   steering mid-run. `insufficient_evidence` was delivered UNCONDITIONALLY (never
 *   gated by the risk threshold) — the judge's least-confident verdict was the one
 *   guaranteed to demand a verification turn. `decided` lived in memory only; the
 *   persisted ledger was written but never read back, so every restart re-armed
 *   re-adjudication; guard-suppressed notes were resurrected from the advisor JSONL;
 *   and full-ledger appendEntry copies made persistence O(n^2) (~1MB for 94 notes).
 *
 * v2 contract:
 *   - OFF by default (`enabled`): when armed, it may only DELAY/DOWNGRADE/SUPPRESS
 *     advice routed via the native advisor channel — never add wake-ups.
 *   - Fail-QUIET: court unavailable/no key -> nothing is injected (v1 fail-opened
 *     every note through as act); one session notification replaces the storm.
 *   - Delivery: `aside` while a run is active, `nextTurn` when idle (no triggerTurn,
 *     so a late verdict never starts a session turn); NEVER `steer`.
 *   - Budgets: per-minute sliding window + per-session cap + per-minute visible
 *     status. Over budget -> ledger only.
 *   - Stop-aware: an explicit owner stop message suppresses all non-high-risk
 *     deliveries until the next real instruction; suppression is announced once
 *     in-transcript.
 *   - Reconciliation: notes already visible in the primary transcript (native
 *     `<advisory>` or earlier verdict) are not re-sent; near-duplicate re-raises of
 *     a decided note reuse the verdict (advisor guard resets can't resurrect).
 *   - Durable decisions: one compact `com.jev-court.decision` record per
 *     adjudication; rebuilt from the session branch on start, so ignores/dups
 *     survive restarts.
 *   - Verdict wording is non-mandatory: "act if useful / skip without audit; no
 *     acknowledgement turn required" — the verification obligation itself is the
 *     loop fuel (#35 symptom 4 + owner direction 2026-09-29).
 *
 * Config: ~/.omp/agent/jev-court.json (all optional):
 *   enabled (default false), dryRun, baseUrl, path, model, apiKey, tickMs,
 *   suppressIgnored, thresholds {high, medium, low}, riskKeywords {high, low},
 *   sessionDeliveryBudget (15), deliveriesPerMinute (2), stopSuppression (true).
 * Key resolution: config apiKey -> OPENROUTER_API_KEY -> read-only agent.db lookup.
 */

import { Database } from "bun:sqlite"; // platform: bundled Bun runtime only; failure is handled
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";

interface CourtConfig {
  enabled: boolean;
  dryRun: boolean;
  baseUrl: string;
  path: string;
  model: string;
  apiKey?: string;
  tickMs: number;
  suppressIgnored: boolean;
  thresholds: { high: number; medium: number; low: number };
  riskKeywords: { high: RegExp[]; low: RegExp[] };
  sessionDeliveryBudget: number;
  deliveriesPerMinute: number;
  stopSuppression: boolean;
}

type RiskTier = "high" | "medium" | "low";
type VerdictChoice = "act" | "ignore" | "insufficient_evidence";

interface Verdict {
  choice: VerdictChoice;
  confidence: number;
  risk: RiskTier;
  model: string;
}

interface AdviseNote {
  advisor: string;
  severity: string;
  text: string;
  provenance: string[];
  key: string;
  sig: string;
}

interface RawEntry {
  timestamp?: number;
  message?: {
    role?: string;
    content?: unknown;
    isError?: boolean;
  };
}

const BASE_CONFIG: CourtConfig = {
  enabled: false, // #35: opt-in only; native advisor channel is the default
  dryRun: false,
  baseUrl: "https://openrouter.ai/api/alpha",
  path: "/decisions",
  model: "typesafe/jev-1.13",
  tickMs: 2000,
  suppressIgnored: true,
  thresholds: { high: 0.9, medium: 0.75, low: 0.6 },
  riskKeywords: {
    high: [
      "\\bdelete\\b", "\\bdrop\\b", "migration", "force-?push", "\\brelease\\b",
      "security", "credential", "secret", "public api", "breaking",
      "canonical", "protocol", "schema", "\\bci\\b", "\\bmerge\\b",
    ].map((s) => new RegExp(s, "i")),
    low: [
      "naming", "typo", "wording", "comment", "format(ting)?",
      "lint", "style", "readme", "cosmetic",
    ].map((s) => new RegExp(s, "i")),
  },
  sessionDeliveryBudget: 15,
  deliveriesPerMinute: 2,
  stopSuppression: true,
};

async function readJson(v: string): Promise<Record<string, unknown>> {
  try {
    return (await Bun.file(v).json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function compileKeywords(list: unknown, fallback: RegExp[]): RegExp[] {
  if (!Array.isArray(list)) return fallback;
  return list.map((s) => new RegExp(String(s), "i"));
}

function toConfig(raw: Record<string, unknown>): CourtConfig {
  const thresholdsRaw = (raw.thresholds ?? {}) as Partial<CourtConfig["thresholds"]>;
  const riskRaw = (raw.riskKeywords ?? {}) as Partial<Record<"high" | "low", unknown>>;
  return {
    ...BASE_CONFIG,
    ...raw,
    thresholds: { ...BASE_CONFIG.thresholds, ...thresholdsRaw },
    riskKeywords: {
      high: compileKeywords(riskRaw.high, BASE_CONFIG.riskKeywords.high),
      low: compileKeywords(riskRaw.low, BASE_CONFIG.riskKeywords.low),
    },
  } satisfies CourtConfig;
}

function normalizeText(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKC")
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// First 8 normalized words: catches re-raised notes whose tail wording changed.
function noteSig(text: string): string {
  return normalizeText(text).split(" ").slice(0, 8).join(" ");
}

function riskTierOf(text: string, cfg: CourtConfig): RiskTier {
  if (cfg.riskKeywords.high.some((re) => re.test(text))) return "high";
  if (cfg.riskKeywords.low.some((re) => re.test(text))) return "low";
  return "medium";
}

function parseEntry(line: string): RawEntry | undefined {
  try {
    const v: unknown = JSON.parse(line);
    if (v && typeof v === "object" && "message" in v) return v as RawEntry;
  } catch {
    /* skip malformed line */
  }
  return undefined;
}

function contentBlocks(content: unknown): Array<Record<string, unknown>> {
  return Array.isArray(content) ? (content as Array<Record<string, unknown>>) : [];
}

function callArgs(block: Record<string, unknown>): Record<string, unknown> {
  const a = block.arguments ?? block.input;
  return a && typeof a === "object" ? (a as Record<string, unknown>) : {};
}

function resultText(msg: NonNullable<RawEntry["message"]>): string {
  for (const b of contentBlocks(msg.content))
    if (b.type === "text" && typeof b.text === "string") return b.text;
  return "";
}

export default function (pi: ExtensionAPI) {
  pi.setLabel("JEV Court v2 — advisor adjudication (opt-in)");

  let cfg: CourtConfig = BASE_CONFIG;
  let apiKey: string | undefined;
  let sessionFile: string | undefined;
  let advisorDir: string | undefined;
  let extCtx: ExtensionContext | undefined;
  const offsets = new Map<string, number>();
  const carryBytes = new Map<string, Uint8Array>();
  const decoder = new TextDecoder("utf-8");
  const provenance = new Map<string, string[]>();
  const seen = new Set<string>();
  const decided = new Map<string, Verdict>();
  const sigIndex = new Map<string, Verdict>(); // advisor+sig -> prior verdict (re-raise reuse)
  const inFlight = new Set<string>();
  const ledger: Array<{ ts: number; key: string; verdict: Verdict; outcome: string; note: string }> = [];

  // #35 durable decisions: rebuild from compact per-decision records on the branch.
  function rehydrate(ctx: ExtensionContext) {
    try {
      const sm = ctx.sessionManager as unknown as { getBranch?: () => Array<Record<string, unknown>> };
      if (typeof sm.getBranch !== "function") return;
      let rehydratedCount = 0;
      for (const e of sm.getBranch()) {
        if (e.type !== "custom" || e.customType !== "com.jev-court.decision") continue;
        const d = e.data as
          | { key?: string; sig?: string; choice?: VerdictChoice; confidence?: number; risk?: RiskTier; model?: string; outcome?: string; ts?: number }
          | undefined;
        if (!d?.key || !d.choice) continue;
        const v: Verdict = {
          choice: d.choice,
          confidence: typeof d.confidence === "number" ? d.confidence : 0,
          risk: (d.risk ?? "medium") as RiskTier,
          model: d.model ?? "rehydrated",
        };
        decided.set(d.key, v);
        seen.add(d.key);
        if (d.sig) sigIndex.set(d.sig, v);
        rehydratedCount++;
      }
      if (rehydratedCount)
        pi.logger?.info?.(`jev-court: rehydrated ${rehydratedCount} prior decisions (${decided.size} keys) from session branch`);
    } catch (e) {
      pi.logger?.warn?.(`jev-court: rehydrate failed: ${String(e)}`);
    }
  }
  async function resolveKey(): Promise<string | undefined> {
    if (typeof cfg.apiKey === "string" && cfg.apiKey) return cfg.apiKey;
    if (process.env.OPENROUTER_API_KEY) return process.env.OPENROUTER_API_KEY;
    try {
      const agentDir =
        process.env.PI_CODING_AGENT_DIR ?? `${process.env.HOME}/.omp/agent`;
      const db = new Database(`${agentDir}/agent.db`, { readonly: true });
      try {
        const row = db
          .query(
            "select data from auth_credentials where provider = 'openrouter' limit 1",
          )
          .get() as { data: string } | null;
        if (row) {
          const parsed: unknown = JSON.parse(row.data);
          if (parsed && typeof parsed === "object" && "key" in parsed)
            return String((parsed as { key: unknown }).key);
        }
      } finally {
        db.close();
      }
    } catch (e) {
      pi.logger?.warn?.(`jev-court: key lookup failed: ${String(e)}`);
    }
    return undefined;
  }

  // ---------- owner stop flag (input hook is OBSERVATION-ONLY: return nothing) ----------
  let ownerStopped = false;
  let stopAnnounced = false;
  let passthroughAnnounced = false;
  // Bare-interjection stops only: "stop", "Stop.", "halt!" — never "stop the timer
  // in the code" (false positive would suppress legit advisories for real work text).
  const STOP_RE =
    /^\s*(?:please\s+|just\s+)?(?:stop|halt|cancel|enough|quit|pause)(?:\s+(?:it|this|that|the\s+(?:loop|session|run)))?\s*[.!…]*\s*$/i;

  pi.on("input", (event: { source?: string; text?: string }) => {
    if (event?.source && event.source !== "interactive") return;
    const text = String(event?.text ?? "");
    if (STOP_RE.test(text)) ownerStopped = true;
    else if (text.trim().length > 12) ownerStopped = false; // next real instruction clears it
    return undefined;
  });

  // ---------- transcript reconciliation ----------
  let transcriptCache: { size: number; text: string } | undefined;
  async function noteInTranscript(text: string): Promise<boolean> {
    if (!sessionFile) return false;
    try {
      const file = Bun.file(sessionFile);
      const size = file.size;
      if (!transcriptCache || transcriptCache.size !== size) {
        const tail = await file.slice(Math.max(0, size - 2_000_000)).text();
        transcriptCache = { size, text: normalizeText(tail) };
      }
      const sig = normalizeText(text).slice(0, 60);
      return sig.length >= 30 && transcriptCache.text.includes(sig);
    } catch {
      return false;
    }
  }

  // ---------- delivery budgets ----------
  let deliveredThisSession = 0;
  const minuteWindow: number[] = [];
  function budgetAllows(): boolean {
    if (deliveredThisSession >= cfg.sessionDeliveryBudget) return false;
    const now = Date.now();
    while (minuteWindow.length && now - minuteWindow[0] > 60_000) minuteWindow.shift();
    return minuteWindow.length < cfg.deliveriesPerMinute;
  }

  // ---------- advisor transcript tailing ----------

  async function listAdvisorFiles(dir: string): Promise<string[]> {
    try {
      const g = new Bun.Glob("__advisor*.jsonl");
      const found: string[] = [];
      for await (const f of g.scan({ cwd: dir, onlyFiles: true }))
        found.push(`${dir}/${f}`);
      return found;
    } catch {
      return [];
    }
  }

  function advisorLabel(file: string): string {
    return file.match(/__advisor(?:\.(.+))?\.jsonl$/)?.[1] ?? "advisor";
  }

  function recordProvenance(file: string, entry: RawEntry) {
    const msg = entry.message;
    if (!msg) return;
    const arr = provenance.get(file) ?? [];
    if (msg.role === "assistant") {
      for (const b of contentBlocks(msg.content)) {
        if (b.type === "toolCall" || b.type === "tool_use") {
          const args = callArgs(b);
          const target =
            args.path ?? args.query ?? args.pattern ?? args.url ?? args.command ?? "";
          arr.push(`${String(b.name)}: ${String(target).slice(0, 120)}`);
        }
      }
    }
    if (msg.role === "toolResult") {
      const ok = msg.isError ? "FAILED" : "ok";
      arr.push(`result(${ok}): ${resultText(msg).replace(/\n/g, " ").slice(0, 160)}`);
    }
    provenance.set(file, arr.slice(-12));
  }

  function harvestNotes(file: string, entry: RawEntry) {
    const msg = entry.message;
    if (!msg || msg.role !== "assistant") return;
    for (const b of contentBlocks(msg.content)) {
      if ((b.type !== "toolCall" && b.type !== "tool_use") || b.name !== "advise")
        continue;
      const args = callArgs(b);
      const text = typeof args.note === "string" ? args.note : "";
      if (!text) continue;
      const advisor = advisorLabel(file);
      const key = `${advisor}::${normalizeText(text).slice(0, 240)}`;
      if (seen.has(key) || decided.has(key) || inFlight.has(key)) continue;
      const sigKey = `${advisor}::${noteSig(text)}`;
      const prior = sigIndex.get(sigKey);
      if (prior) {
        // Re-raised finding (possibly reworded after an advisor guard reset):
        // reuse the prior verdict; never re-adjudicate, never re-deliver.
        seen.add(key);
        decided.set(key, prior);
        record(key, sigKey, prior, "revive_suppressed", text);
        continue;
      }
      seen.add(key);
      inFlight.add(key);
      const note: AdviseNote = {
        advisor,
        severity: typeof args.severity === "string" ? args.severity : "nit",
        text: text.slice(0, 4000),
        provenance: (provenance.get(file) ?? []).slice(-6),
        key,
        sig: sigKey,
      };
      adjudicate(note).finally(() => inFlight.delete(key));
    }
  }

  async function tick() {
    if (!advisorDir) return;
    for (const f of await listAdvisorFiles(advisorDir)) {
      const file = Bun.file(f);
      const size = file.size;
      const prev = offsets.get(f);
      if (prev === undefined) {
        offsets.set(f, size); // seed at EOF
        continue;
      }
      if (size < prev) {
        offsets.set(f, 0); // rewritten/truncated
        carryBytes.set(f, new Uint8Array(0));
      }
      const start = offsets.get(f) ?? size;
      if (size === start && (carryBytes.get(f)?.length ?? 0) === 0) continue;
      // Byte-exact tailing: offsets track BYTES; decode only up to the last
      // complete line (multibyte notes must not be sliced mid-character).
      const fresh = new Uint8Array(await file.slice(start).arrayBuffer());
      offsets.set(f, start + fresh.length);
      const prevCarry = carryBytes.get(f);
      let all: Uint8Array = fresh;
      if (prevCarry && prevCarry.length) {
        all = new Uint8Array(prevCarry.length + fresh.length);
        all.set(prevCarry);
        all.set(fresh, prevCarry.length);
      }
      let cut = 0;
      for (let i = all.length - 1; i >= 0; i--) {
        if (all[i] === 0x0a) {
          cut = i + 1;
          break;
        }
      }
      carryBytes.set(f, all.subarray(cut));
      if (cut === 0) continue;
      const lines = decoder.decode(all.subarray(0, cut)).split("\n");
      for (const line of lines) {
        if (!line.trim()) continue;
        const entry = parseEntry(line);
        if (!entry) continue;
        recordProvenance(f, entry);
        harvestNotes(f, entry);
      }
    }
  }

  // ---------- primary context digest ----------

  async function primaryDigest(): Promise<string> {
    if (!sessionFile) return "";
    try {
      const file = Bun.file(sessionFile);
      const tail = await file.slice(Math.max(0, file.size - 262_144)).text();
      const lines = tail.split("\n");
      const texts: string[] = [];
      for (let i = lines.length - 1; i >= 0 && texts.length < 4; i--) {
        const entry = parseEntry(lines[i]);
        const msg = entry?.message;
        if (msg?.role !== "assistant") continue;
        for (const b of contentBlocks(msg.content))
          if (b.type === "text" && typeof b.text === "string" && b.text.trim())
            texts.push(b.text.trim().slice(0, 400));
      }
      return texts.reverse().join("\n---\n");
    } catch {
      return "";
    }
  }

  // ---------- JEV adjudication ----------

  async function adjudicate(note: AdviseNote) {
    const risk = riskTierOf(note.text, cfg);
    const state = [
      "DISPUTE CHUNK (mechanical, generated by jev-court)",
      `MAIN AGENT recent output:\n${(await primaryDigest()).slice(0, 1600) || "(none captured)"}`,
      `\nADVISOR "${note.advisor}" criticism (severity=${note.severity}):\n${note.text}`,
      `\nADVISOR PROVENANCE (tool activity during that review):\n${
        note.provenance.length
          ? note.provenance.map((p) => `- ${p}`).join("\n")
          : "- none recorded"
      }`,
    ].join("\n");

    if (!apiKey) {
      // Fail-QUIET (#35): with no court, notes stay on the native guarded channel.
      decide(note, { choice: "ignore", confidence: 0, risk, model: "no-key" }, true);
      return;
    }
    // Concurrency gate: storm bursts (v1 saw 94 notes fire at once) must not
    // hammer the decisions API; excess adjudications queue FIFO.
    await courtGate();
    let verdict: Verdict;
    try {
      const res = await fetch(`${cfg.baseUrl}${cfg.path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: cfg.model,
          state,
          questions: {
            verdict: {
              type: "choice",
              instructions:
                "Decide the main agent's next action regarding this advisor criticism.",
              criteria: {
                act: "criticism is evidence-backed and acting now improves correctness or speed",
                ignore:
                  "criticism is wrong, already handled, cosmetic, or acting would waste effort",
                insufficient_evidence:
                  "neither side shows a runnable check; suggest verification without demanding it",
              },
            },
          },
        }),
        signal: AbortSignal.timeout(15_000),
      });
      if (!res.ok) throw new Error(`jev http ${res.status}`);
      const j: unknown = await res.json();
      const answers =
        j && typeof j === "object" && "answers" in j
          ? ((j as { answers: Record<string, unknown> }).answers.verdict ?? {})
          : {};
      const a = answers as Record<string, unknown>;
      const rawChoice = String(a.choice ?? "");
      const choice: VerdictChoice =
        rawChoice === "act" || rawChoice === "ignore" || rawChoice === "insufficient_evidence"
          ? rawChoice
          : "insufficient_evidence";
      verdict = {
        choice,
        confidence: typeof a.confidence === "number" ? a.confidence : 0,
        risk,
        model:
          j && typeof j === "object" && "model" in j
            ? String((j as { model: unknown }).model)
            : cfg.model,
      };
    } catch (e) {
      // Fail-QUIET: court error must not turn into an unscored act message.
      pi.logger?.warn?.(`jev-court: adjudication failed (${String(e)}); note stays native-only`);
      courtGateRelease();
      decide(note, { choice: "ignore", confidence: 0, risk, model: "court-error" }, true);
      return;
    }
    courtGateRelease();
    decide(note, verdict, false);
  }
  // ---------- adjudication concurrency gate ----------
  const MAX_CONCURRENT_COURT_CALLS = 3;
  let courtSlots = 0;
  const courtQueue: Array<() => void> = [];
  async function courtGate(): Promise<void> {
    if (courtSlots < MAX_CONCURRENT_COURT_CALLS) {
      courtSlots++;
      return;
    }
    await new Promise<void>((resolve) =>
      courtQueue.push(() => {
        courtSlots++;
        resolve();
      }),
    );
  }
  function courtGateRelease(): void {
    courtSlots--;
    courtQueue.shift()?.();
  }

  function record(key: string, sig: string, v: Verdict, outcome: string, note: string) {
    try {
      pi.appendEntry("com.jev-court.decision", {
        key: key.slice(0, 260),
        sig: sig.slice(0, 160),
        choice: v.choice,
        confidence: v.confidence,
        risk: v.risk,
        model: v.model,
        outcome,
        ts: Date.now(),
      });
    } catch {
      /* before runtime init: memory-only */
    }
    ledger.push({ ts: Date.now(), key: key.slice(0, 80), verdict: v, outcome, note: note.slice(0, 140) });
    if (ledger.length > 400) ledger.splice(0, ledger.length - 400);
  }

  function decide(note: AdviseNote, v: Verdict, passthrough: boolean) {
    decided.set(note.key, v);
    sigIndex.set(note.sig, v);

    if (passthrough) {
      record(note.key, note.sig, v, "quiet_passthrough", note.text);
      if (!passthroughAnnounced) {
        passthroughAnnounced = true;
        extCtx?.ui.notify?.(
          "jev-court: court unavailable — advisor notes are left to the native guarded channel (nothing injected)",
          "warning",
        );
      }
      return; // v2 fail-QUIET: no unscored injections
    }

    if (cfg.dryRun) {
      record(note.key, note.sig, v, "dry_run", note.text);
      return;
    }
    const thr = cfg.thresholds[v.risk];
    if (v.choice === "ignore") {
      if (cfg.suppressIgnored) {
        record(note.key, note.sig, v, "suppressed_ignore", note.text);
        return;
      }
      deliver(note, v, "ignore_note"); // deliver() records the outcome
      return;
    }
    if (v.choice === "act" && v.confidence < thr) {
      record(note.key, note.sig, v, "below_threshold", note.text); // v1 silently dropped; now auditable
      return;
    }
    void route(note, v);
  }


  async function route(note: AdviseNote, v: Verdict) {
    if (await noteInTranscript(note.text)) {
      record(note.key, note.sig, v, "dup_in_transcript", note.text);
      return; // native <advisory>/earlier verdict already visible: silent
    }
    deliver(note, v, v.choice === "insufficient_evidence" ? "demand" : "act");
  }

  function deliver(note: AdviseNote, v: Verdict, mode: "act" | "demand" | "ignore_note") {
    if (cfg.stopSuppression && ownerStopped && v.risk !== "high") {
      record(note.key, note.sig, v, "stop_suppressed", note.text);
      if (!stopAnnounced && extCtx) {
        stopAnnounced = true;
        extCtx.ui.notify?.("jev-court: owner stop in effect — non-critical advisories suppressed (ledger only)", "info");
      }
      return;
    }
    if (!budgetAllows()) {
      record(note.key, note.sig, v, "budget_suppressed", note.text);
      return;
    }
    deliveredThisSession++;
    minuteWindow.push(Date.now());
    const head =
      mode === "demand"
        ? `[jev-court ${v.risk}, conf ${v.confidence.toFixed(2)}] VERDICT=insufficient_evidence — OPTIONAL check before acting on this note; proceeding without it is allowed; no acknowledgement turn required:`
        : mode === "ignore_note"
          ? `[jev-court ${v.risk}] court VERDICT=ignore — you may skip this advisor note without auditing it; no acknowledgement required:`
          : `[jev-court ${v.risk}, conf ${v.confidence.toFixed(2)}] VERDICT=act — advisory only: act if useful, skip without audit; no acknowledgement turn required:`;
    const idle = extCtx?.isIdle?.() ?? true;
    pi.sendMessage(
      { customType: "com.jev-court.verdict", content: `${head}\n\n${note.text}` },
      // #35: never steer; when idle use nextTurn (surfaced on the owner's next
      // prompt) so a late verdict cannot wake the session.
      { deliverAs: idle ? "nextTurn" : "aside" },
    );
    record(note.key, note.sig, v, `delivered_${mode}`, note.text);
  }

  // ---------- wiring ----------

  function deriveDirs(ctx: ExtensionContext) {
    const sm = ctx.sessionManager as unknown as {
      getSessionFile?: () => string;
      getArtifactsDir?: () => string;
    };
    sessionFile =
      typeof sm.getSessionFile === "function" ? sm.getSessionFile() : undefined;
    if (typeof sm.getArtifactsDir === "function" && sm.getArtifactsDir()) {
      advisorDir = sm.getArtifactsDir();
    } else if (sessionFile) {
      advisorDir = sessionFile.replace(/\.jsonl$/, "");
    } else {
      advisorDir = undefined;
    }
  }

  pi.on("session_start", async (_e, ctx: ExtensionContext) => {
    extCtx = ctx;
    cfg = toConfig(await readJson(`${process.env.PI_CODING_AGENT_DIR ?? `${process.env.HOME}/.omp/agent`}/jev-court.json`));
    if (!cfg.enabled) return;
    deriveDirs(ctx);
    rehydrate(ctx);
    apiKey = await resolveKey();
    if (!apiKey)
      ctx.ui.notify(
        "jev-court: no OpenRouter key; court is quiet — advisor notes stay on the native channel",
        "warning",
      );
    if (!advisorDir) {
      ctx.ui.notify("jev-court: cannot locate advisor transcript dir; idle", "warning");
      return;
    }
    ctx.setInterval(() => {
      tick().catch(() => {});
    }, cfg.tickMs);
    ctx.ui.notify(
      `jev-court v2 armed → ${cfg.model} · budget ${cfg.deliveriesPerMinute}/min · ${decided.size} decisions rehydrated · ${ownerStopped ? "stop-suppressed" : "live"}`,
      "info",
    );
  });

  pi.on("session_switch", (_e, ctx: ExtensionContext) => {
    extCtx = ctx;
    deriveDirs(ctx);
    offsets.clear();
    carryBytes.clear();
    provenance.clear();
    inFlight.clear();
    transcriptCache = undefined;
    // decided/seen/sigIndex intentionally SURVIVE the switch (v1 lost the map only
    // across processes; same fix applies here) — budget counters do not reset.
  });

  pi.registerCommand("jev", {
    description: "JEV court v2 status: config, budget use, recent decisions",
    handler: async (_args, ctx: ExtensionContext) => {
      const tally: Record<string, number> = {};
      for (const l of ledger) tally[l.outcome] = (tally[l.outcome] ?? 0) + 1;
      const recent = ledger
        .slice(-8)
        .reverse()
        .map(
          (l) =>
            `${new Date(l.ts).toLocaleTimeString()} ${l.outcome} [${l.verdict.risk}] ${l.verdict.choice}@${l.verdict.confidence.toFixed(2)} :: ${l.note.slice(0, 80)}`,
        );
      ctx.ui.notify(
        `jev-court ${cfg.enabled ? (cfg.dryRun ? "(dry-run)" : "armed") : "DISABLED (default)"} · delivered ${deliveredThisSession}/${cfg.sessionDeliveryBudget} · stop=${ownerStopped ? "ACTIVE" : "off"} · ${JSON.stringify(tally)}\n${recent.join("\n")}`,
        "info",
      );
    },
  });
}


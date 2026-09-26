/**
 * jev-court — mechanical advisor adjudication pipeline.
 *
 * Flow (all in-process, no chat polling):
 *   1. Tail the advisor transcript JSONL (`__advisor*.jsonl`) under the session
 *      artifacts directory, seeded at EOF so historical notes are never re-run.
 *   2. Chunk each `advise` note with mechanical provenance (the advisor's own tool
 *      calls/results during that review) plus a tail digest of the primary's output.
 *   3. POST to TypeSafe Jev via the OpenRouter decisions API
 *      (`{model,state,questions}` → typed choice + probability + confidence).
 *   4. Route by risk-tiered confidence threshold:
 *        act  + conf >= tier threshold → deliver (blocker=steer, else aside)
 *        ignore                        → suppress (ledger only) unless suppressIgnored=false
 *        insufficient_evidence         → deliver a demand-for-runnable-check instead
 *      Fail-open: court error → note passes through with the original severity.
 *   Decisions are remembered by normalized-note key, so advisor context resets
 *   (which clear the advisor's own dedupe guard) cannot resurrect a decided claim.
 *
 * Config: ~/.omp/agent/jev-court.json (all optional):
 *   enabled, dryRun, baseUrl, model, apiKey, tickMs, suppressIgnored,
 *   thresholds {high, medium, low}, riskKeywords {high: string[], low: string[]}
 *   (keyword strings are compiled as case-insensitive regex sources).
 * Key resolution: config apiKey → OPENROUTER_API_KEY → read-only agent.db lookup.
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
  enabled: true,
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
  pi.setLabel("JEV Court — advisor adjudication");

  let cfg: CourtConfig = BASE_CONFIG;
  let apiKey: string | undefined;
  let sessionFile: string | undefined;
  let advisorDir: string | undefined;
  const offsets = new Map<string, number>();
  const provenance = new Map<string, string[]>();
  const seen = new Set<string>();
  const decided = new Map<string, Verdict>();
  const inFlight = new Set<string>();
  const ledger: Array<{ ts: number; key: string; verdict: Verdict; note: string }> = [];

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
      seen.add(key);
      inFlight.add(key);
      const note: AdviseNote = {
        advisor,
        severity: typeof args.severity === "string" ? args.severity : "nit",
        text: text.slice(0, 4000),
        provenance: (provenance.get(file) ?? []).slice(-6),
        key,
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
      if (size < prev) offsets.set(f, 0); // rewritten/truncated
      const start = offsets.get(f) ?? size;
      if (size === start) continue;
      offsets.set(f, size);
      const chunk = (await file.text()).slice(start);
      const lines = chunk.split("\n");
      for (const line of lines.slice(0, -1)) {
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
      decide(note, { choice: "act", confidence: 0, risk, model: "no-key" }, true);
      return;
    }

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
                  "neither side shows a runnable check; demand verification instead of deciding",
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
      // Fail-open: court unavailable → original advisor routing stands.
      pi.logger?.warn?.(`jev-court: adjudication failed (${String(e)}); passing note through`);
      decide(note, { choice: "act", confidence: 0, risk, model: "court-error" }, true);
      return;
    }
    decide(note, verdict, false);
  }

  function decide(note: AdviseNote, v: Verdict, passthrough: boolean) {
    decided.set(note.key, v);
    ledger.push({ ts: Date.now(), key: note.key.slice(0, 80), verdict: v, note: note.text.slice(0, 140) });
    try {
      pi.appendEntry("com.jev-court.ledger", ledger.slice(-200));
    } catch {
      /* before runtime init: memory-only */
    }

    const thr = cfg.thresholds[v.risk];
    if (cfg.dryRun) return;
    if (passthrough || v.choice === "insufficient_evidence") {
      deliver(note, v, v.choice === "insufficient_evidence");
    } else if (v.choice === "act" && v.confidence >= thr) {
      deliver(note, v, false);
    } else if (v.choice === "ignore" && !cfg.suppressIgnored) {
      deliver(note, v, false); // override: ignored notes still posted as dimmed asides
    } // else: ignore → suppressed, ledger only
  }

  function deliver(note: AdviseNote, v: Verdict, demandCheck: boolean) {
    const head =
      v.model === "court-error" || v.model === "no-key"
        ? `[jev-court] court unavailable — advisor note passes through unscored:`
        : demandCheck
          ? `[jev-court ${v.risk} risk, confidence ${v.confidence.toFixed(2)}] VERDICT=insufficient_evidence — run a check before acting on this advisor note:`
          : `[jev-court ${v.risk} risk, confidence ${v.confidence.toFixed(2)}] VERDICT=act — follow this advisor note:`;
    pi.sendMessage(
      { customType: "com.jev-court.verdict", content: `${head}\n\n${note.text}` },
      { deliverAs: note.severity === "blocker" && !demandCheck ? "steer" : "aside" },
    );
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
    cfg = toConfig(await readJson(`${process.env.PI_CODING_AGENT_DIR ?? `${process.env.HOME}/.omp/agent`}/jev-court.json`));
    if (!cfg.enabled) return;
    deriveDirs(ctx);
    apiKey = await resolveKey();
    if (!apiKey)
      ctx.ui.notify(
        "jev-court: no OpenRouter key; advisor notes pass through unadjudicated",
        "warning",
      );
    if (!advisorDir) {
      ctx.ui.notify("jev-court: cannot locate advisor transcript dir; idle", "warning");
      return;
    }
    ctx.setInterval(() => {
      tick().catch(() => {});
    }, cfg.tickMs);
    ctx.ui.notify(`jev-court armed → ${cfg.model} @ ${cfg.baseUrl}`, "info");
  });

  pi.on("session_switch", (_e, ctx: ExtensionContext) => {
    deriveDirs(ctx);
    offsets.clear();
    provenance.clear();
    inFlight.clear();
  });

  pi.registerCommand("jev", {
    description: "JEV court status: config, tallies, recent verdicts",
    handler: async (_args, ctx: ExtensionContext) => {
      const tally: Record<string, number> = {};
      for (const l of ledger) tally[l.verdict.choice] = (tally[l.verdict.choice] ?? 0) + 1;
      const recent = ledger
        .slice(-8)
        .reverse()
        .map(
          (l) =>
            `${new Date(l.ts).toLocaleTimeString()} [${l.verdict.risk}] ${l.verdict.choice}@${l.verdict.confidence.toFixed(2)} :: ${l.note.slice(0, 90)}`,
        );
      ctx.ui.notify(
        `jev-court ${cfg.dryRun ? "(dry-run) " : ""}${apiKey ? "armed" : "NO KEY"} · ${cfg.model} · decided=${ledger.length} ${JSON.stringify(tally)}\n${recent.join("\n")}`,
        "info",
      );
    },
  });
}

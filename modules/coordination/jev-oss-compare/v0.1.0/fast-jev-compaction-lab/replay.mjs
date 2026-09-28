#!/usr/bin/env node
/**
 * Local-only adapter experiment for tamaratran/fast-jev-compaction.
 * Default mode is content-free planning; local inference requires
 * --execute-local and an Ollama model/digest pair explicitly supplied by the
 * caller. This runner never imports or calls the package's hosted Jev client.
 */
import { createHash, randomUUID } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compact, reductionRatio } from 'fast-jev-compaction';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '../../../../../');
const DEFAULT_BASE_URL = process.env.FAST_JEV_OLLAMA_BASE_URL ?? 'http://127.0.0.1:11435';
const DEFAULT_CTX = 9216;
const DEFAULT_KEEP_THRESHOLD = 0.5;
const NO_THINK_CHAT = '<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n';
const YES_NO = [
  { id: 'yes', description: 'The stated proposition is true.' },
  { id: 'no', description: 'The stated proposition is false.' },
];

function parseArgs(argv) {
  const args = { executeLocal: false, baseUrl: DEFAULT_BASE_URL, keepThreshold: DEFAULT_KEEP_THRESHOLD,
    maxStateTokens: 6000, maxRequestTokens: 8000, preserveRecentMessages: 6, truncateHeadChars: 300 };
  const names = new Map([
    ['--input', 'input'], ['--output', 'output'], ['--base-url', 'baseUrl'], ['--model', 'model'],
    ['--expected-digest', 'expectedDigest'], ['--goal', 'goal'], ['--max-state-tokens', 'maxStateTokens'],
    ['--max-request-tokens', 'maxRequestTokens'], ['--preserve-recent-messages', 'preserveRecentMessages'],
    ['--keep-threshold', 'keepThreshold'], ['--truncate-head-chars', 'truncateHeadChars'], ['--run-id', 'runId'],
  ]);
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === '--execute-local') { args.executeLocal = true; continue; }
    if (key === '--help' || key === '-h') { args.help = true; continue; }
    const target = names.get(key);
    if (!target || i + 1 >= argv.length || argv[i + 1].startsWith('--')) throw new Error('invalid_arguments');
    args[target] = argv[++i];
  }
  for (const key of ['maxStateTokens', 'maxRequestTokens', 'preserveRecentMessages', 'truncateHeadChars']) {
    args[key] = Number(args[key]);
    if (!Number.isInteger(args[key]) || args[key] < 0) throw new Error('invalid_numeric_option');
  }
  args.keepThreshold = Number(args.keepThreshold);
  if (!Number.isFinite(args.keepThreshold) || args.keepThreshold < 0 || args.keepThreshold > 1) {
    throw new Error('invalid_keep_threshold');
  }
  if (args.maxStateTokens < 1 || args.maxRequestTokens < args.maxStateTokens || args.maxRequestTokens > DEFAULT_CTX) {
    throw new Error('invalid_context_budget_for_local_model');
  }
  if (args.runId !== undefined && (!/^[A-Za-z0-9_.:-]{1,128}$/.test(args.runId))) throw new Error('invalid_run_id');
  return args;
}

function usage() {
  return [
    'Usage: node replay.mjs --input <normalized-stream.json> --output <private-receipt.json> [options]',
    'Default is a content-free plan with no model request. Add --execute-local for local Ollama inference.',
    'Options: --base-url http://127.0.0.1:11435 --model <exact-local-model> --expected-digest <sha256>',
    '         --goal <text> --max-state-tokens 6000 --max-request-tokens 8000',
    '         --preserve-recent-messages 6 --keep-threshold 0.5 --truncate-head-chars 300 --run-id <unique-attempt-id>',
  ].join('\n');
}

function isWithin(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function validateMessages(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || value.schema_version !== 1 || !Array.isArray(value.messages)) {
    throw new Error('input_schema_invalid');
  }
  if (value.messages.length === 0) throw new Error('input_messages_empty');
  const allowedMessage = new Set(['role', 'text', 'toolUses', 'toolResults']);
  const calls = new Set();
  const results = new Set();
  for (const message of value.messages) {
    if (!message || typeof message !== 'object' || Array.isArray(message) ||
        Object.keys(message).some((key) => !allowedMessage.has(key)) ||
        !['user', 'assistant'].includes(message.role) || typeof message.text !== 'string' ||
        !Array.isArray(message.toolUses) || (message.toolResults !== undefined && !Array.isArray(message.toolResults))) {
      throw new Error('input_message_shape_invalid');
    }
    for (const tool of message.toolUses) {
      if (!tool || typeof tool !== 'object' || Array.isArray(tool) ||
          Object.keys(tool).some((key) => !['tool_use_id', 'tool', 'input', 'text', 'isError'].includes(key)) ||
          typeof tool.tool_use_id !== 'string' || !tool.tool_use_id || typeof tool.tool !== 'string' ||
          !tool.tool || !tool.input || typeof tool.input !== 'object' || Array.isArray(tool.input) ||
          (tool.text !== undefined && typeof tool.text !== 'string') ||
          (tool.isError !== undefined && typeof tool.isError !== 'boolean') || calls.has(tool.tool_use_id)) {
        throw new Error('input_tool_use_invalid');
      }
      calls.add(tool.tool_use_id);
    }
    for (const result of message.toolResults ?? []) {
      if (!result || typeof result !== 'object' || Array.isArray(result) ||
          Object.keys(result).some((key) => !['tool_use_id', 'text', 'isError'].includes(key)) ||
          typeof result.tool_use_id !== 'string' || !result.tool_use_id || typeof result.text !== 'string' ||
          (result.isError !== undefined && typeof result.isError !== 'boolean') || results.has(result.tool_use_id)) {
        throw new Error('input_tool_result_invalid');
      }
      results.add(result.tool_use_id);
    }
  }
  if (calls.size !== results.size || [...calls].some((id) => !results.has(id))) throw new Error('tool_pair_coverage_incomplete');
  return value.messages;
}

function textFingerprint(messages) {
  // Hash only ordered, non-empty user/assistant text fields; never persist text.
  const rows = messages.filter((m) => m.text.length > 0).map(({ role, text }) => ({ role, text }));
  return { sha256: createHash('sha256').update(JSON.stringify(rows), 'utf8').digest('hex'), count: rows.length };
}

function defaultGoal(messages) {
  return messages.filter((message) => message.role === 'user' && message.text.trim().length > 0 &&
    (message.toolResults ?? []).length === 0).slice(-3).map((message) =>
    message.text.length <= 500 ? message.text : `${message.text.slice(0, 499)}…`).join('\n');
}

function localBaseUrl(raw) {
  let url;
  try { url = new URL(raw); } catch { throw new Error('local_endpoint_invalid'); }
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]', '::1'].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash || (url.pathname !== '/' && url.pathname !== '')) {
    throw new Error('endpoint_must_be_loopback_http');
  }
  return url.origin;
}

async function requestJson(url, payload, timeoutMs = 600_000) {
  const response = await fetch(url, {
    method: payload === undefined ? 'GET' : 'POST',
    headers: payload === undefined ? { accept: 'application/json' } : { 'content-type': 'application/json', accept: 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
    redirect: 'error',
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`ollama_http_${response.status}`);
  const value = await response.json();
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('ollama_response_invalid');
  return value;
}

function renderOpenJevPrompt(state, instructions) {
  const stateText = typeof state === 'string' ? state : JSON.stringify(state);
  const task = {
    primitive: 'noul',
    instructions,
    criteria: YES_NO.map((candidate, index) => ({ label: index === 0 ? 'A' : 'B', description: candidate.description })),
  };
  const prompt = `Shared state:\n${stateText}\n\n${JSON.stringify(task)}\nReturn only the selected letter: A, B.\nAnswer:`;
  return NO_THINK_CHAT.replace('{prompt}', prompt);
}

function probabilitiesFromLogprobs(data) {
  const rows = data?.logprobs?.[0]?.top_logprobs;
  if (!Array.isArray(rows)) throw new Error('openjev_logprob_schema_missing');
  const values = new Map(rows.map((row) => [String(row.token), Number(row.logprob)]));
  if (!Number.isFinite(values.get('A')) || !Number.isFinite(values.get('B'))) {
    throw new Error('openjev_yes_no_distribution_incomplete');
  }
  const max = Math.max(values.get('A'), values.get('B'));
  const yesWeight = Math.exp(values.get('A') - max);
  const noWeight = Math.exp(values.get('B') - max);
  return yesWeight / (yesWeight + noWeight);
}

class LocalOpenJevAsker {
  constructor({ baseUrl, model, contextTokens }) {
    this.baseUrl = baseUrl;
    this.model = model;
    this.contextTokens = contextTokens;
    this.requests = 0;
    this.responsesValidated = 0;
    this.ms = [];
    this.queue = Promise.resolve(); // package batches in parallel; keep local inference serial.
  }

  async ask(state, questions) {
    const job = this.queue.then(() => this.#askSerial(state, questions));
    this.queue = job.catch(() => {});
    return job;
  }

  async #askSerial(state, questions) {
    const answers = {};
    for (const [name, question] of Object.entries(questions)) {
      if (!question || question.type !== 'noul' || typeof question.instructions !== 'string') {
        throw new Error('upstream_question_contract_unsupported');
      }
      const started = performance.now();
      this.requests += 1;
      const result = await requestJson(`${this.baseUrl}/api/generate`, {
        model: this.model,
        prompt: renderOpenJevPrompt(state, question.instructions),
        raw: true,
        stream: false,
        think: false,
        logprobs: true,
        top_logprobs: 20,
        options: { temperature: 0, num_predict: 1, num_ctx: this.contextTokens },
      });
      const pYes = probabilitiesFromLogprobs(result);
      answers[name] = { type: 'noul', noul: pYes };
      this.responsesValidated += 1;
      this.ms.push(performance.now() - started);
    }
    return { model: this.model, answers };
  }
}

async function verifyModel(baseUrl, model, expectedDigest) {
  const inventory = await requestJson(`${baseUrl}/api/tags`);
  if (!Array.isArray(inventory.models)) throw new Error('ollama_inventory_invalid');
  const selected = inventory.models.find((row) => row?.name === model);
  if (!selected) throw new Error('configured_model_not_in_local_inventory');
  if (selected.digest !== expectedDigest) throw new Error('model_digest_mismatch');
  return { name: selected.name, digest: selected.digest, size: selected.size ?? null };
}

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * p))];
}

async function writeReceipt(file, value) {
  const target = path.resolve(file);
  if (isWithin(target, REPO_ROOT)) throw new Error('output_must_be_outside_repository');
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx' });
  return target;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { process.stdout.write(`${usage()}\n`); return 0; }
  if (!args.input || !args.output) throw new Error('input_and_output_required');
  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  if (isWithin(inputPath, REPO_ROOT) || isWithin(outputPath, REPO_ROOT)) throw new Error('input_and_output_must_be_outside_repository');
  const raw = await readFile(inputPath);
  const document = JSON.parse(raw.toString('utf8'));
  const messages = validateMessages(document);
  const userAssistant = textFingerprint(messages);
  const sourceHash = createHash('sha256').update(raw).digest('hex');
  const effectiveGoal = args.goal ?? defaultGoal(messages);
  const counts = {
    messages: messages.length,
    userMessages: messages.filter((m) => m.role === 'user').length,
    assistantMessages: messages.filter((m) => m.role === 'assistant').length,
    userAssistantTextMessages: userAssistant.count,
    toolUses: messages.reduce((sum, m) => sum + m.toolUses.length, 0),
    toolResults: messages.reduce((sum, m) => sum + (m.toolResults?.length ?? 0), 0),
  };
  const runId = args.runId ?? randomUUID();
  const runIdentity = {
    source_sha256: sourceHash,
    upstream_package: 'fast-jev-compaction@0.4.1',
    model: { name: args.model ?? null, expected_digest: args.expectedDigest ?? null, verified_digest: null },
    settings: {
      goal_sha256: createHash('sha256').update(effectiveGoal, 'utf8').digest('hex'),
      keepThreshold: args.keepThreshold,
      preserveRecentMessages: args.preserveRecentMessages,
      maxStateTokens: args.maxStateTokens,
      maxRequestTokens: args.maxRequestTokens,
      truncateHeadChars: args.truncateHeadChars,
      numCtx: DEFAULT_CTX,
    },
  };
  const receipt = {
    schema_version: 1,
    adapter: 'fast-jev-compaction-openjev-local',
    upstream_library: 'fast-jev-compaction@0.4.1',
    run_id: runId,
    run_identity_sha256: createHash('sha256').update(JSON.stringify(runIdentity)).digest('hex'),
    run_identity: runIdentity,
    source_sha256: sourceHash,
    status: args.executeLocal ? 'starting' : 'planned',
    inference_called: false,
    content_included: false,
    content_preservation: { nonempty_user_assistant_text_sha256: userAssistant.sha256, ...counts },
    model: null,
    semantics: {
      probability: 'OpenJev A/B candidate-normalized top-20 logprobs; uncalibrated and not Jev-calibrated confidence',
      cost: 'no hosted API billing; local electricity/runtime cost not measured',
      context: `fast-jev token estimates; local num_ctx=${DEFAULT_CTX}`,
      normalization: 'one pre-normalized stream in upstream Message[] shape; no raw transcript parser or sidechain stitching',
    },
  };
  if (!args.executeLocal) {
    receipt.status = 'planned';
    receipt.limits = { maxStateTokens: args.maxStateTokens, maxRequestTokens: args.maxRequestTokens,
      preserveRecentMessages: args.preserveRecentMessages, keepThreshold: args.keepThreshold };
    await writeReceipt(args.output, receipt);
    process.stdout.write(`${JSON.stringify({ status: receipt.status, inference_called: false, content_included: false, counts, source_sha256: sourceHash })}\n`);
    return 0;
  }
  if (!args.model || !args.expectedDigest) throw new Error('execute_requires_exact_model_and_digest');
  const baseUrl = localBaseUrl(args.baseUrl);
  let asker = null;
  try {
    const identity = await verifyModel(baseUrl, args.model, args.expectedDigest);
    receipt.model = identity;
    runIdentity.model.verified_digest = identity.digest;
    receipt.run_identity_sha256 = createHash('sha256').update(JSON.stringify(runIdentity)).digest('hex');
    receipt.run_identity = runIdentity;
    asker = new LocalOpenJevAsker({ baseUrl, model: args.model, contextTokens: DEFAULT_CTX });
    const result = await compact(messages, asker, {
      goal: args.goal,
      keepThreshold: args.keepThreshold,
      preserveRecentMessages: args.preserveRecentMessages,
      maxStateTokens: args.maxStateTokens,
      maxRequestTokens: args.maxRequestTokens,
      truncateHeadChars: args.truncateHeadChars,
    });
    const afterText = textFingerprint(result.messages);
    const unchanged = userAssistant.sha256 === afterText.sha256 && userAssistant.count === afterText.count;
    const actions = { keep: 0, drop_result: 0, drop_call: 0 };
    for (const decision of result.decisions) actions[decision.action] = (actions[decision.action] ?? 0) + 1;
    receipt.status = unchanged ? 'complete' : 'failed_closed';
    receipt.inference_called = asker.requests > 0;
    receipt.content_preservation = { ...receipt.content_preservation, unchanged,
      text_message_count_after: afterText.count };
    receipt.compaction = {
      stats: result.stats,
      reduction_ratio: reductionRatio(result),
      decision_action_counts: actions,
      openjev_requests: asker.requests,
      openjev_responses_validated: asker.responsesValidated,
      openjev_latency_ms: { median: percentile(asker.ms, 0.5), p95: percentile(asker.ms, 0.95) },
      decision_probability_semantics: 'noul=true is locally softmax-normalized over A/B top-token logprobs; no calibration claim',
    };
    if (!unchanged) receipt.failure = 'user_assistant_text_fingerprint_changed';
  } catch (error) {
    receipt.status = 'failed_closed';
    receipt.inference_called = (asker?.requests ?? 0) > 0;
    receipt.failure = String(error?.message ?? 'local_run_failed').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 100);
  }
  await writeReceipt(args.output, receipt);
  process.stdout.write(`${JSON.stringify({ status: receipt.status, inference_called: receipt.inference_called,
    content_included: false, source_sha256: sourceHash, run_id: receipt.run_id,
    run_identity_sha256: receipt.run_identity_sha256, counts, failure: receipt.failure ?? null })}\n`);
  return receipt.status === 'complete' ? 0 : 1;
}

main().then((code) => { process.exitCode = code; }).catch((error) => {
  const failure = String(error?.message ?? 'runner_failed').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 100);
  process.stderr.write(`${JSON.stringify({ status: 'rejected', failure, content_included: false })}\n`);
  process.exitCode = 2;
});

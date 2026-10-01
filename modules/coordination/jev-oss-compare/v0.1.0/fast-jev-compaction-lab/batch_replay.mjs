#!/usr/bin/env node
/**
 * Sequential batch wrapper for prepared fast-jev-compaction inputs.
 *
 * The default is a content-free plan. Local inference and endpoint checks
 * happen only after --execute-local. No transcript or model answer is stored
 * in this wrapper's aggregate log.
 */
import { createHash, randomUUID } from 'node:crypto';
import { readFile, readdir, mkdir, appendFile, stat } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '../../../../../');
const UPSTREAM = 'fast-jev-compaction@0.4.1';
const NUM_CTX = 9216;
const SHA256_RE = /^[a-f0-9]{64}$/i;

const sha = (value) => createHash('sha256').update(value).digest('hex');
const canonical = (value) => JSON.stringify(value, (_key, nested) => {
  if (!nested || typeof nested !== 'object' || Array.isArray(nested)) return nested;
  return Object.fromEntries(Object.keys(nested).sort().map((key) => [key, nested[key]]));
});

function usage() {
  return [
    'Usage: node batch_replay.mjs --corpus-receipt <prepared-corpus.json> --input-dir <normalized-dir> --work-dir <private-run-dir> --mode full|boundaries|all --base-url <loopback-url> --model <exact-name> --expected-digest <sha256> [options]',
    'Default is a content-free plan; it makes zero endpoint calls. Add --execute-local to verify the model and run serially.',
    'Options: --max-state-tokens 6000 --max-request-tokens 8000 --preserve-recent-messages 6',
    '         --keep-threshold 0.5 --truncate-head-chars 300 --execute-local',
  ].join('\n');
}

function parseArgs(argv) {
  const args = { executeLocal: false, maxStateTokens: 6000, maxRequestTokens: 8000,
    preserveRecentMessages: 6, keepThreshold: 0.5, truncateHeadChars: 300 };
  const values = new Map([
    ['--corpus-receipt', 'corpusReceipt'], ['--input-dir', 'inputDir'], ['--work-dir', 'workDir'],
    ['--mode', 'mode'], ['--base-url', 'baseUrl'], ['--model', 'model'], ['--expected-digest', 'expectedDigest'],
    ['--max-state-tokens', 'maxStateTokens'], ['--max-request-tokens', 'maxRequestTokens'],
    ['--preserve-recent-messages', 'preserveRecentMessages'], ['--keep-threshold', 'keepThreshold'],
    ['--truncate-head-chars', 'truncateHeadChars'],
  ]);
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === '--help' || key === '-h') { args.help = true; continue; }
    if (key === '--execute-local') { args.executeLocal = true; continue; }
    const field = values.get(key);
    if (!field || i + 1 >= argv.length || argv[i + 1].startsWith('--')) throw new Error('invalid_arguments');
    args[field] = argv[++i];
  }
  for (const key of ['maxStateTokens', 'maxRequestTokens', 'preserveRecentMessages', 'truncateHeadChars']) {
    args[key] = Number(args[key]);
    if (!Number.isInteger(args[key]) || args[key] < 0) throw new Error(`invalid_${key}`);
  }
  args.keepThreshold = Number(args.keepThreshold);
  if (args.maxStateTokens < 1 || args.maxRequestTokens < args.maxStateTokens || args.maxRequestTokens > NUM_CTX ||
      !Number.isFinite(args.keepThreshold) || args.keepThreshold < 0 || args.keepThreshold > 1) throw new Error('invalid_compaction_settings');
  if (!args.help && (!args.corpusReceipt || !args.inputDir || !args.workDir || !['full', 'boundaries', 'all'].includes(args.mode) ||
      !args.baseUrl || !args.model || !args.expectedDigest)) throw new Error('required_options_missing');
  if (!args.help && !SHA256_RE.test(args.expectedDigest)) throw new Error('invalid_expected_digest');
  if (!args.help && (typeof args.model !== 'string' || !args.model.trim() || args.model.length > 240)) throw new Error('invalid_model_name');
  return args;
}

function within(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
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

function defaultGoal(messages) {
  return messages.filter((message) => message.role === 'user' && message.text.trim().length > 0 &&
    (message.toolResults ?? []).length === 0).slice(-3).map((message) =>
    message.text.length <= 500 ? message.text : `${message.text.slice(0, 499)}…`).join('\n');
}

function messageFingerprint(messages) {
  const rows = messages.map((message) => ({
    role: message.role,
    text: message.text,
    toolUses: message.toolUses.map(({ tool_use_id, tool, input }) => ({ tool_use_id, tool, input })),
    toolResults: (message.toolResults ?? []).map(({ tool_use_id, text, isError }) => ({ tool_use_id, text, isError: isError ?? false })),
  }));
  return sha(canonical(rows));
}

function validateMessages(document) {
  if (!document || typeof document !== 'object' || Array.isArray(document) || document.schema_version !== 1 || !Array.isArray(document.messages) || document.messages.length === 0) {
    throw new Error('input_schema_invalid');
  }
  const calls = new Set();
  const results = new Set();
  const allowedMessage = new Set(['role', 'text', 'toolUses', 'toolResults']);
  for (const message of document.messages) {
    if (!message || typeof message !== 'object' || Array.isArray(message) ||
        Object.keys(message).some((key) => !allowedMessage.has(key)) || !['user', 'assistant'].includes(message.role) ||
        typeof message.text !== 'string' || !Array.isArray(message.toolUses) ||
        (message.toolResults !== undefined && !Array.isArray(message.toolResults))) throw new Error('input_message_shape_invalid');
    for (const tool of message.toolUses) {
      if (!tool || typeof tool !== 'object' || Array.isArray(tool) ||
          Object.keys(tool).some((key) => !['tool_use_id', 'tool', 'input', 'text', 'isError'].includes(key)) ||
          typeof tool.tool_use_id !== 'string' || !tool.tool_use_id || typeof tool.tool !== 'string' || !tool.tool ||
          !tool.input || typeof tool.input !== 'object' || Array.isArray(tool.input) ||
          (tool.text !== undefined && typeof tool.text !== 'string') ||
          (tool.isError !== undefined && typeof tool.isError !== 'boolean') || calls.has(tool.tool_use_id)) throw new Error('input_tool_use_invalid');
      calls.add(tool.tool_use_id);
    }
    for (const result of message.toolResults ?? []) {
      if (!result || typeof result !== 'object' || Array.isArray(result) ||
          Object.keys(result).some((key) => !['tool_use_id', 'text', 'isError'].includes(key)) ||
          typeof result.tool_use_id !== 'string' || !result.tool_use_id || typeof result.text !== 'string' ||
          (result.isError !== undefined && typeof result.isError !== 'boolean') || results.has(result.tool_use_id)) throw new Error('input_tool_result_invalid');
      results.add(result.tool_use_id);
    }
  }
  if (calls.size !== results.size || [...calls].some((id) => !results.has(id))) throw new Error('tool_pair_coverage_incomplete');
  return document.messages;
}

function safeArtifactName(value) {
  return typeof value === 'string' && value.length > 0 && value.length < 200 &&
    path.basename(value) === value && !value.includes('..') && !/[\\/:]/.test(value);
}

async function readPreparedInput(inputDir, row, boundary) {
  if (!safeArtifactName(row.artifact_name)) throw new Error('artifact_name_invalid');
  const file = path.resolve(inputDir, row.artifact_name);
  if (!within(file, inputDir)) throw new Error('artifact_path_escape');
  const bytes = await readFile(file);
  const document = JSON.parse(bytes.toString('utf8'));
  const messages = validateMessages(document);
  const fileSha = sha(bytes);
  const expectedSource = boundary ? row.prefix_sha256 : row.normalized_stream_sha256;
  const verifiedSource = boundary ? messageFingerprint(messages) : sha(JSON.stringify(document));
  if (expectedSource !== verifiedSource) throw new Error('prepared_input_hash_mismatch');
  const expectedIdentitySource = row.run_identity?.source_or_prefix_sha256;
  if (!SHA256_RE.test(expectedIdentitySource ?? '') || expectedIdentitySource !== verifiedSource) throw new Error('prepared_run_identity_source_mismatch');
  const callIds = new Set(messages.flatMap((message) => message.toolUses.map((tool) => tool.tool_use_id)));
  const resultIds = new Set(messages.flatMap((message) => (message.toolResults ?? []).map((tool) => tool.tool_use_id)));
  if (callIds.size !== resultIds.size || [...callIds].some((id) => !resultIds.has(id))) throw new Error('prepared_tool_pairs_mismatch');
  return { file, bytes, messages, fileSha, verifiedSource };
}

function inputRows(corpus, mode) {
  if (!corpus || corpus.schema_version !== 1 || corpus.tool !== 'fast-jev-compaction-corpus-planner' ||
      corpus.status !== 'prepared' || corpus.inference_called !== false || corpus.transcript_content_included !== false || !Array.isArray(corpus.streams)) {
    throw new Error('prepared_corpus_receipt_invalid');
  }
  const rows = [];
  const validatePlanIdentity = (row) => {
    if (!row.run_identity || typeof row.run_identity !== 'object' || !SHA256_RE.test(row.run_identity_sha256 ?? '') ||
        sha(canonical(row.run_identity)) !== row.run_identity_sha256) throw new Error('prepared_run_identity_invalid');
  };
  for (const stream of corpus.streams) {
    if (mode !== 'boundaries' && stream.prepared === true && stream.eligible_for_execution === true) {
      validatePlanIdentity(stream);
      if (typeof stream.stream_id !== 'string' || !stream.stream_id) throw new Error('prepared_stream_identity_invalid');
      rows.push({ kind: 'full', streamId: stream.stream_id, artifact_name: stream.artifact_name,
        normalized_stream_sha256: stream.normalized_stream_sha256, run_identity: stream.run_identity,
        count: stream.counts?.adapterHttpRequests ?? null });
    }
    if (mode !== 'full') for (const boundary of stream.boundaries ?? []) {
      if (boundary.eligible_for_execution === true) {
        validatePlanIdentity(boundary);
        if (typeof stream.stream_id !== 'string' || !stream.stream_id || typeof boundary.boundary_id !== 'string' || !boundary.boundary_id) {
          throw new Error('prepared_boundary_identity_invalid');
        }
        rows.push({ kind: 'boundary', streamId: stream.stream_id,
        boundaryId: boundary.boundary_id, artifact_name: boundary.artifact_name, prefix_sha256: boundary.prefix_sha256,
        run_identity: boundary.run_identity, count: boundary.counts?.adapterHttpRequests ?? null });
      }
    }
  }
  if (!rows.length) throw new Error('no_eligible_inputs_for_mode');
  rows.sort((a, b) => `${a.streamId}:${a.kind}:${a.boundaryId ?? ''}`.localeCompare(`${b.streamId}:${b.kind}:${b.boundaryId ?? ''}`, 'en'));
  return rows;
}

function configIdentity(messages, sourceSha, args) {
  const goal = defaultGoal(messages);
  return {
    source_sha256: sourceSha,
    upstream_package: UPSTREAM,
    model: { name: args.model, expected_digest: args.expectedDigest, verified_digest: args.expectedDigest },
    settings: {
      goal_sha256: sha(goal),
      keepThreshold: args.keepThreshold,
      preserveRecentMessages: args.preserveRecentMessages,
      maxStateTokens: args.maxStateTokens,
      maxRequestTokens: args.maxRequestTokens,
      truncateHeadChars: args.truncateHeadChars,
      numCtx: NUM_CTX,
    },
  };
}

function identityFor(row, loaded, args) {
  const identity = configIdentity(loaded.messages, loaded.fileSha, args);
  const identitySha = sha(JSON.stringify(identity));
  const snapshotIdentity = `${row.streamId}:${row.kind}:${row.boundaryId ?? 'full'}`;
  const runId = `fc_${sha(`${identitySha}\0${snapshotIdentity}`).slice(0, 40)}`;
  const requestEstimate = estimateRequests(loaded.messages, args.preserveRecentMessages);
  return { identity, identitySha, runId, requestEstimate };
}

function estimateRequests(messages, preserveRecent) {
  const resultIndex = new Map();
  messages.forEach((message, index) => {
    for (const result of message.toolResults ?? []) resultIndex.set(result.tool_use_id, index);
  });
  let candidates = 0;
  messages.forEach((message, callIndex) => {
    for (const tool of message.toolUses) {
      const resultAt = resultIndex.get(tool.tool_use_id);
      if (resultAt === undefined) continue;
      const pinned = callIndex === 0 || callIndex >= messages.length - preserveRecent ||
        resultAt === 0 || resultAt >= messages.length - preserveRecent;
      if (!pinned) candidates += 1;
    }
  });
  return candidates * 2;
}

async function readAggregate(file) {
  try { await stat(file); } catch (error) { if (error?.code === 'ENOENT') return []; throw error; }
  const text = await readFile(file, 'utf8');
  if (!text) return [];
  const rows = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue;
    let row;
    try { row = JSON.parse(line); } catch { throw new Error('aggregate_log_invalid_json'); }
    if (!row || row.schema_version !== 1 || typeof row.run_identity_sha256 !== 'string' || typeof row.status !== 'string') {
      throw new Error('aggregate_log_invalid_row');
    }
    rows.push(row);
  }
  return rows;
}

async function appendAggregate(file, row) {
  await mkdir(path.dirname(file), { recursive: true });
  await appendFile(file, `${JSON.stringify(row)}\n`, { encoding: 'utf8', flag: 'a' });
}

async function validCompletedReceipt(workDir, rows, identity, identitySha, runId) {
  const candidates = rows.filter((row) => row.run_identity_sha256 === identitySha && row.status === 'complete' &&
    row.run_id === runId && typeof row.receipt_file === 'string').reverse();
  const names = candidates.map((row) => row.receipt_file);
  try {
    for (const name of await readdir(path.join(workDir, 'receipts'))) {
      if (name.startsWith(`${runId}-attempt-`) && name.endsWith('.json')) names.push(name);
    }
  } catch (error) { if (error?.code !== 'ENOENT') throw error; }
  for (const name of [...new Set(names)].reverse()) {
    if (!safeArtifactName(name)) continue;
    try {
      const raw = await readFile(path.join(workDir, 'receipts', name));
      const receipt = JSON.parse(raw.toString('utf8'));
      if (receipt.status === 'complete' && receipt.inference_called === true &&
          receipt.run_id === runId && receipt.run_identity_sha256 === identitySha &&
          receipt.source_sha256 === identity.source_sha256 && receipt.model?.name === identity.model.name &&
          receipt.model?.digest === identity.model.expected_digest && receipt.content_included === false) return { receipt_file: name, receipt };
    } catch { /* A missing/corrupt prior receipt is not treated as complete. */ }
  }
  return null;
}

async function verifyEndpoint(baseUrl, model, expectedDigest) {
  const response = await fetch(`${baseUrl}/api/tags`, { method: 'GET', headers: { accept: 'application/json' },
    redirect: 'error', signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new Error('model_inventory_http_failure');
  const inventory = await response.json();
  if (!Array.isArray(inventory?.models)) throw new Error('model_inventory_invalid');
  const selected = inventory.models.find((entry) => entry?.name === model);
  if (!selected) throw new Error('model_not_in_local_inventory');
  if (selected.digest !== expectedDigest) throw new Error('model_digest_mismatch');
  return { name: selected.name, digest: selected.digest };
}

function childRun(input, receiptFile, args, runId) {
  const commandArgs = [
    path.join(SCRIPT_DIR, 'replay.mjs'), '--input', input, '--output', receiptFile,
    '--base-url', args.baseUrl, '--model', args.model, '--expected-digest', args.expectedDigest,
    '--max-state-tokens', String(args.maxStateTokens), '--max-request-tokens', String(args.maxRequestTokens),
    '--preserve-recent-messages', String(args.preserveRecentMessages), '--keep-threshold', String(args.keepThreshold),
    '--truncate-head-chars', String(args.truncateHeadChars), '--run-id', runId, '--execute-local',
  ];
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, commandArgs, { cwd: SCRIPT_DIR, stdio: 'ignore', windowsHide: true });
    child.once('error', () => reject(new Error('adapter_process_start_failed')));
    child.once('close', (code) => resolve(code));
  });
}

async function writeReceiptAttempt(receiptsDir, runId, attempt) {
  await mkdir(receiptsDir, { recursive: true });
  return path.join(receiptsDir, `${runId}-attempt-${String(attempt).padStart(4, '0')}.json`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { process.stdout.write(`${usage()}\n`); return 0; }
  const corpusReceiptPath = path.resolve(args.corpusReceipt);
  const inputDir = path.resolve(args.inputDir);
  const workDir = path.resolve(args.workDir);
  if (within(corpusReceiptPath, REPO_ROOT) || within(inputDir, REPO_ROOT) || within(workDir, REPO_ROOT)) throw new Error('all_private_paths_must_be_outside_repository');
  if (within(inputDir, workDir) || within(workDir, inputDir)) throw new Error('input_and_work_dirs_must_be_separate');
  const baseUrl = localBaseUrl(args.baseUrl);
  const corpus = JSON.parse((await readFile(corpusReceiptPath)).toString('utf8'));
  const rows = inputRows(corpus, args.mode);
  const selected = [];
  for (const row of rows) {
    const loaded = await readPreparedInput(inputDir, row, row.kind === 'boundary');
    const identity = identityFor(row, loaded, args);
    selected.push({ row, loaded: { file: loaded.file, fileSha: loaded.fileSha }, ...identity });
  }
  if (new Set(selected.map((item) => item.runId)).size !== selected.length) throw new Error('duplicate_logical_snapshot_identity');
  const aggregatePath = path.join(workDir, 'aggregate.jsonl');
  const oldRows = await readAggregate(aggregatePath);
  const pending = [];
  let resumed = 0;
  for (const item of selected) {
    const prior = await validCompletedReceipt(workDir, oldRows, item.identity, item.identitySha, item.runId);
    if (prior) {
      resumed += 1;
      if (!oldRows.some((entry) => entry.run_identity_sha256 === item.identitySha && entry.run_id === item.runId &&
          entry.status === 'complete' && entry.receipt_file === prior.receipt_file)) {
        await appendAggregate(path.join(workDir, 'aggregate.jsonl'), {
          schema_version: 1, run_id: item.runId, run_identity_sha256: item.identitySha, status: 'complete',
          failure_code: null, mode: args.mode, stream_id: item.row.streamId, boundary_id: item.row.boundaryId ?? null,
          source_sha256: item.identity.source_sha256, package: UPSTREAM,
          model: { name: item.identity.model.name, digest: item.identity.model.expected_digest },
          request_count: prior.receipt.compaction?.openjev_requests ?? null,
          adapter_run_identity_sha256: prior.receipt.run_identity_sha256, receipt_file: prior.receipt_file,
          attempt: Number(prior.receipt_file.match(/-attempt-(\d+)\.json$/)?.[1] ?? 0), attempt_id: randomUUID(),
          inference_called: true, recovered_after_interruption: true,
        });
      }
    } else pending.push(item);
  }
  const plan = {
    status: args.executeLocal ? 'ready_to_execute' : 'planned',
    inference_called: false,
    endpoint_calls: 0,
    mode: args.mode,
    lane: { model: args.model, expected_digest: args.expectedDigest, endpoint: 'loopback-only' },
    settings: { maxStateTokens: args.maxStateTokens, maxRequestTokens: args.maxRequestTokens,
      preserveRecentMessages: args.preserveRecentMessages, keepThreshold: args.keepThreshold,
      truncateHeadChars: args.truncateHeadChars, numCtx: NUM_CTX },
    selected_inputs: selected.length,
    pending_inputs: pending.length,
    safely_resumed_complete: resumed,
    estimated_inference_http_requests: pending.reduce((sum, item) => sum + item.requestEstimate, 0),
    logical_inputs: selected.map((item) => ({ run_id: item.runId, run_identity_sha256: item.identitySha,
      stream_id: item.row.streamId, boundary_id: item.row.boundaryId ?? null, estimated_requests: item.requestEstimate })),
    output_log: aggregatePath,
  };
  if (!args.executeLocal) {
    process.stdout.write(`${JSON.stringify(plan)}\n`);
    return 0;
  }
  if (!pending.length) {
    plan.status = 'already_complete';
    plan.safely_resumed_complete = resumed;
    process.stdout.write(`${JSON.stringify(plan)}\n`);
    return 0;
  }
  let verifiedModel;
  try { verifiedModel = await verifyEndpoint(baseUrl, args.model, args.expectedDigest); }
  catch (error) {
    const reason = String(error?.message ?? 'model_preflight_failed').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 100);
    for (const item of pending) await appendAggregate(aggregatePath, {
      schema_version: 1, run_id: item.runId, run_identity_sha256: item.identitySha,
      status: 'failed_model_preflight', failure_code: reason, mode: args.mode,
      stream_id: item.row.streamId, boundary_id: item.row.boundaryId ?? null,
      inference_called: false, endpoint_calls: 1, attempt_id: randomUUID(),
    });
    process.stderr.write(`${JSON.stringify({ status: 'failed_model_preflight', failure_code: reason, inference_called: false })}\n`);
    return 2;
  }
  plan.endpoint_calls = 1;
  plan.verified_model = verifiedModel;
  plan.status = 'running';
  plan.inference_called = true;
  process.stdout.write(`${JSON.stringify({ status: 'running', mode: args.mode, selected_inputs: pending.length,
    model: verifiedModel, inference_called: true, serial: true })}\n`);
  let failures = 0;
  let actualInferenceRequests = 0;
  const receiptsDir = path.join(workDir, 'receipts');
  for (const item of pending) {
    const previous = oldRows.filter((row) => row.run_identity_sha256 === item.identitySha).length;
    let attempt = previous + 1;
    let output = await writeReceiptAttempt(receiptsDir, item.runId, attempt);
    while (await stat(output).then(() => true).catch((error) => { if (error?.code === 'ENOENT') return false; throw error; })) {
      attempt += 1;
      output = await writeReceiptAttempt(receiptsDir, item.runId, attempt);
    }
    const receiptName = path.basename(output);
    const attemptId = randomUUID();
    let exitCode = null;
    let receipt = null;
    let failureCode = null;
    try {
      exitCode = await childRun(item.loaded.file, output, { ...args, baseUrl }, item.runId);
      const rawReceipt = await readFile(output);
      receipt = JSON.parse(rawReceipt.toString('utf8'));
      if (receipt.run_id !== item.runId || receipt.source_sha256 !== item.identity.source_sha256 ||
          receipt.model?.name !== verifiedModel.name || receipt.model?.digest !== verifiedModel.digest ||
          receipt.run_identity_sha256 !== item.identitySha) throw new Error('adapter_receipt_identity_mismatch');
      if (exitCode !== 0 || receipt.status !== 'complete' || receipt.inference_called !== true) failureCode = receipt.failure ?? 'adapter_run_incomplete';
    } catch (error) {
      failureCode = String(error?.message ?? 'adapter_receipt_missing').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 100);
    }
    const complete = failureCode === null;
    if (!complete) failures += 1;
    actualInferenceRequests += receipt?.compaction?.openjev_requests ?? 0;
    await appendAggregate(aggregatePath, {
      schema_version: 1,
      run_id: item.runId,
      run_identity_sha256: item.identitySha,
      status: complete ? 'complete' : 'failed',
      failure_code: failureCode,
      mode: args.mode,
      stream_id: item.row.streamId,
      boundary_id: item.row.boundaryId ?? null,
      source_sha256: item.identity.source_sha256,
      package: UPSTREAM,
      model: { name: verifiedModel.name, digest: verifiedModel.digest },
      request_count: receipt?.compaction?.openjev_requests ?? null,
      adapter_run_identity_sha256: receipt?.run_identity_sha256 ?? null,
      receipt_file: receiptName,
      attempt,
      attempt_id: attemptId,
      inference_called: receipt?.inference_called === true,
    });
    process.stdout.write(`${JSON.stringify({ status: complete ? 'complete' : 'failed', run_id: item.runId,
      run_identity_sha256: item.identitySha, stream_id: item.row.streamId, boundary_id: item.row.boundaryId ?? null,
      failure_code: failureCode, request_count: receipt?.compaction?.openjev_requests ?? null,
      receipt_file: receiptName })}\n`);
  }
  const result = { status: failures === 0 ? 'complete' : 'incomplete', mode: args.mode,
    selected_inputs: pending.length, safely_resumed_complete: resumed, failures,
    inference_called: true, model_identity_checks: 1 + pending.length,
    actual_inference_http_requests: actualInferenceRequests, serial: true, aggregate_log: aggregatePath };
  process.stdout.write(`${JSON.stringify(result)}\n`);
  return failures === 0 ? 0 : 1;
}

main().then((code) => { process.exitCode = code; }).catch((error) => {
  const failure = String(error?.message ?? 'batch_replay_failed').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 120);
  process.stderr.write(`${JSON.stringify({ status: 'rejected', inference_called: false, failure })}\n`);
  process.exitCode = 2;
});

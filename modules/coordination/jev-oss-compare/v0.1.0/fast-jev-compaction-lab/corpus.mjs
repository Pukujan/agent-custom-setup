#!/usr/bin/env node
/**
 * Offline raw-Claude converter and planner for the fast-jev-compaction lab.
 *
 * Default mode is a content-free dry run. `--prepare` writes normalized
 * transcripts/snapshots only to a caller-selected directory outside the repo.
 * This tool never calls a model or invokes replay.mjs.
 */
import { createHash, randomUUID } from 'node:crypto';
import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '../../../../../');
const DEFAULT_RECENT = 6;
const VOLATILE = new Set(['promptId', 'gitBranch', 'origin', 'rendered', 'renderedInHumanTurn']);

const sha = (value) => createHash('sha256').update(value).digest('hex');
const jsonCanonical = (value) => JSON.stringify(value, (_key, nested) => {
  if (!nested || typeof nested !== 'object' || Array.isArray(nested)) return nested;
  return Object.fromEntries(Object.keys(nested).sort().map((key) => [key, nested[key]]));
});
const opaque = (value) => sha(String(value)).slice(0, 20);

function usage() {
  return [
    'Usage: node corpus.mjs --source <raw-claude-jsonl-dir> --receipt <outside-repo.json> [--prepare --output-dir <outside-repo-dir>]',
    'Default: content-free dry run; no normalized transcript files and no model calls.',
    'Prepare: writes one normalized JSON stream and eligible boundary-prefix files per stream.',
    'Options: --preserve-recent-messages 6 --max-state-tokens 6000 --max-request-tokens 8000',
    '         --keep-threshold 0.5 --truncate-head-chars 300 --no-boundary-prefixes',
  ].join('\n');
}

function parseArgs(argv) {
  const args = { prepare: false, boundaries: true, preserveRecent: DEFAULT_RECENT,
    maxStateTokens: 6000, maxRequestTokens: 8000, keepThreshold: 0.5, truncateHeadChars: 300 };
  const values = new Map([
    ['--source', 'source'], ['--receipt', 'receipt'], ['--output-dir', 'outputDir'],
    ['--preserve-recent-messages', 'preserveRecent'], ['--max-state-tokens', 'maxStateTokens'],
    ['--max-request-tokens', 'maxRequestTokens'], ['--keep-threshold', 'keepThreshold'],
    ['--truncate-head-chars', 'truncateHeadChars'],
  ]);
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === '--help' || key === '-h') { args.help = true; continue; }
    if (key === '--prepare') { args.prepare = true; continue; }
    if (key === '--no-boundary-prefixes') { args.boundaries = false; continue; }
    const field = values.get(key);
    if (!field || i + 1 >= argv.length || argv[i + 1].startsWith('--')) throw new Error('invalid_arguments');
    args[field] = argv[++i];
  }
  args.preserveRecent = Number(args.preserveRecent);
  if (!Number.isInteger(args.preserveRecent) || args.preserveRecent < 0) throw new Error('invalid_recent_message_count');
  for (const key of ['maxStateTokens', 'maxRequestTokens', 'truncateHeadChars']) {
    args[key] = Number(args[key]);
    if (!Number.isInteger(args[key]) || args[key] < 0) throw new Error(`invalid_${key}`);
  }
  args.keepThreshold = Number(args.keepThreshold);
  if (args.maxStateTokens < 1 || args.maxRequestTokens < args.maxStateTokens || args.maxRequestTokens > 9216 ||
      !Number.isFinite(args.keepThreshold) || args.keepThreshold < 0 || args.keepThreshold > 1) throw new Error('invalid_compaction_settings');
  if (!args.help && (!args.source || !args.receipt)) throw new Error('source_and_receipt_required');
  if (args.prepare && !args.outputDir) throw new Error('prepare_requires_output_dir');
  return args;
}

function isWithin(candidate, parent) {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

async function listJsonl(root) {
  const result = [];
  async function walk(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name, 'en'));
    for (const entry of entries) {
      if (entry.name.startsWith('.') || ['node_modules', 'fixtures', 'fixture', 'gold', 'harvest', 'reports'].includes(entry.name.toLowerCase())) continue;
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(file);
      else if (entry.isFile() && entry.name.toLowerCase().endsWith('.jsonl')) result.push(file);
    }
  }
  await walk(root);
  return result;
}

function cleanForDedupe(value) {
  if (Array.isArray(value)) return value.map(cleanForDedupe);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.keys(value).filter((key) => !VOLATILE.has(key))
    .sort().map((key) => [key, cleanForDedupe(value[key])]));
}

function streamIdentity(row, relativeFile) {
  const session = String(row.sessionId ?? row.session_id ?? path.basename(relativeFile, '.jsonl'));
  const sidechain = Boolean(row.isSidechain);
  const agent = row.agentId == null ? '' : String(row.agentId);
  return { session, sidechain, agent, relativeFile: sidechain && !agent ? relativeFile : '' };
}

function identityKey(id) {
  return JSON.stringify([id.session, id.sidechain, id.agent, id.relativeFile]);
}

function extractText(value, errors, where) {
  if (typeof value === 'string') return value;
  if (!Array.isArray(value)) {
    errors.push(`${where}_unsupported_text_shape`);
    return '';
  }
  let out = '';
  for (const block of value) {
    if (typeof block === 'string') { out += block; continue; }
    if (!block || typeof block !== 'object') { errors.push(`${where}_unsupported_content_block`); continue; }
    if (block.type === 'text' && typeof block.text === 'string') out += block.text;
    else if (['thinking', 'redacted_thinking', 'signature'].includes(block.type)) {
      // Upstream Message has no representation for these non-user-visible blocks.
      continue;
    } else errors.push(`${where}_unsupported_content_block`);
  }
  return out;
}

function extractToolResultContent(value, errors) {
  if (typeof value === 'string') return value;
  if (!Array.isArray(value)) {
    errors.push('tool_result_content_unsupported');
    return '';
  }
  let out = '';
  for (const block of value) {
    if (typeof block === 'string') out += block;
    else if (block && block.type === 'text' && typeof block.text === 'string') out += block.text;
    else errors.push('tool_result_block_unsupported');
  }
  return out;
}

function normalizeRow(row, provenance, errors) {
  const type = String(row.type ?? '').toLowerCase();
  if (type === 'system' && String(row.subtype ?? '').toLowerCase() === 'compact_boundary') {
    return { boundary: true, uuid: String(row.uuid ?? ''), parentUuid: row.parentUuid == null ? null : String(row.parentUuid),
      location: provenance, timestamp: String(row.timestamp ?? ''), stream: streamIdentity(row, provenance.relativeFile),
      preserved: row.compactMetadata?.preservedMessages ?? null };
  }
  const sourceMessage = row.message && typeof row.message === 'object' ? row.message : null;
  const role = String(sourceMessage?.role ?? type).toLowerCase();
  if (!['user', 'human', 'assistant'].includes(role)) return null;
  if (row.isMeta || row.isSidechain && role === 'user' && row.isMeta) return null;
  const content = sourceMessage?.content ?? row.content;
  const blocks = Array.isArray(content) ? content : [content];
  const message = {
    role: role === 'human' ? 'user' : role,
    text: '',
    toolUses: [],
    _uuid: String(row.uuid ?? ''),
    _parentUuid: row.parentUuid == null ? null : String(row.parentUuid),
    _timestamp: String(row.timestamp ?? ''),
    _location: provenance,
    _stream: streamIdentity(row, provenance.relativeFile),
    _contentKinds: [],
  };
  for (const block of blocks) {
    if (typeof block === 'string') { message.text += block; message._contentKinds.push('string'); continue; }
    if (!block || typeof block !== 'object') { errors.push('message_block_invalid'); continue; }
    const kind = String(block.type ?? 'unknown');
    message._contentKinds.push(kind);
    if (kind === 'text') {
      if (typeof block.text !== 'string') errors.push('text_block_invalid');
      else message.text += block.text;
    } else if (kind === 'tool_use') {
      const input = block.input ?? {};
      if (typeof block.id !== 'string' || !block.id || typeof block.name !== 'string' || !block.name ||
          !input || typeof input !== 'object' || Array.isArray(input)) errors.push('tool_use_invalid');
      else message.toolUses.push({ tool_use_id: block.id, tool: block.name, input });
    } else if (kind === 'tool_result') {
      if (typeof block.tool_use_id !== 'string' || !block.tool_use_id) errors.push('tool_result_id_missing');
      else {
        const text = extractToolResultContent(block.content ?? '', errors);
        message.toolResults ??= [];
        message.toolResults.push({ tool_use_id: block.tool_use_id, text, ...(block.is_error === true ? { isError: true } : {}) });
      }
    } else if (['thinking', 'redacted_thinking', 'signature'].includes(kind)) {
      // Deliberately excluded: these have no representation in the upstream Message contract.
    } else {
      errors.push(`message_block_unsupported_${kind.replace(/[^a-z0-9_-]/gi, '_').slice(0, 24)}`);
    }
  }
  return message;
}

async function readSources(root, files) {
  const groups = new Map();
  const boundaries = new Map();
  const report = { sourceFiles: files.length, sourceBytes: 0, sourceRows: 0, malformedRows: 0,
    duplicateRowsCollapsed: 0, conflictingDuplicateUuids: 0, sourceHashes: [], errors: {},
    crossStreamParentLinks: 0, unresolvedParentLinks: 0, sourceOnlyParentLinks: 0, ambiguousParentLinks: 0 };
  const seen = new Map();
  const sourceUuidStreams = new Map();
  for (const file of files) {
    const raw = await readFile(file);
    const fileHash = sha(raw);
    const relativeFile = path.relative(root, file).split(path.sep).join('/');
    report.sourceBytes += raw.length;
    report.sourceHashes.push({ path_sha256: sha(relativeFile), sha256: fileHash, bytes: raw.length });
    const lines = raw.toString('utf8').split(/\r?\n/);
    for (let i = 0; i < lines.length; i += 1) {
      if (!lines[i]) continue;
      report.sourceRows += 1;
      let row;
      try { row = JSON.parse(lines[i]); }
      catch { report.malformedRows += 1; continue; }
      if (!row || typeof row !== 'object' || Array.isArray(row)) { report.malformedRows += 1; continue; }
      const location = { sourceFileSha256: fileHash, relativeFile, line: i + 1 };
      const id = streamIdentity(row, relativeFile);
      const key = identityKey(id);
      if (row.uuid != null && String(row.uuid)) {
        const sourceOwners = sourceUuidStreams.get(String(row.uuid)) ?? new Set();
        sourceOwners.add(key);
        sourceUuidStreams.set(String(row.uuid), sourceOwners);
      }
      const errors = [];
      const normalized = normalizeRow(row, location, errors);
      for (const error of errors) report.errors[error] = (report.errors[error] ?? 0) + 1;
      if (normalized?.boundary) {
        const list = boundaries.get(key) ?? [];
        list.push(normalized);
        boundaries.set(key, list);
        continue;
      }
      if (!normalized) continue;
      normalized._errors = errors;
      const uuid = normalized._uuid;
      if (uuid) {
        const duplicateKey = `${key}\0${uuid}`;
        const canonical = jsonCanonical(cleanForDedupe(row));
        const prior = seen.get(duplicateKey);
        if (prior !== undefined) {
          if (prior === canonical) { report.duplicateRowsCollapsed += 1; continue; }
          report.conflictingDuplicateUuids += 1;
          normalized._errors.push('duplicate_uuid_conflict');
          report.errors.duplicate_uuid_conflict = (report.errors.duplicate_uuid_conflict ?? 0) + 1;
        } else seen.set(duplicateKey, canonical);
      }
      const list = groups.get(key) ?? { identity: id, messages: [], rows: [] };
      list.messages.push(normalized);
      list.rows.push({ uuid, parentUuid: normalized._parentUuid, location, timestamp: normalized._timestamp });
      groups.set(key, list);
    }
  }
  for (const [key, group] of groups) {
    group.messages.sort((a, b) => compareLocation(a._location, b._location));
    const ids = new Set(group.messages.map((m) => m._uuid).filter(Boolean));
    const externalRefs = group.messages.map((m) => m._parentUuid).filter((parent) => parent && !ids.has(parent));
    group.crossStreamParentLinks = externalRefs.filter((parent) => [...(sourceUuidStreams.get(parent) ?? [])].some((owner) => owner !== key));
    group.sourceOnlyParentIds = externalRefs.filter((parent) => sourceUuidStreams.get(parent)?.has(key));
    group.unresolvedParentIds = externalRefs.filter((parent) => !(sourceUuidStreams.get(parent)?.size));
    group.ambiguousParentLinks = externalRefs.filter((parent) => (sourceUuidStreams.get(parent)?.size ?? 0) > 1);
    report.crossStreamParentLinks += group.crossStreamParentLinks.length;
    report.sourceOnlyParentLinks += group.sourceOnlyParentIds.length;
    report.unresolvedParentLinks += group.unresolvedParentIds.length;
    report.ambiguousParentLinks += group.ambiguousParentLinks.length;
  }
  return { groups, boundaries, report };
}

function compareLocation(a, b) {
  if (a.timestamp && b.timestamp && a.timestamp !== b.timestamp) return a.timestamp.localeCompare(b.timestamp, 'en');
  const fileOrder = a.relativeFile.localeCompare(b.relativeFile, 'en');
  if (fileOrder !== 0) return fileOrder;
  return a.line - b.line;
}

function messageFingerprint(messages) {
  const rows = messages.map((m) => ({ role: m.role, text: m.text,
    toolUses: m.toolUses.map((x) => ({ tool_use_id: x.tool_use_id, tool: x.tool, input: x.input })),
    toolResults: (m.toolResults ?? []).map((x) => ({ tool_use_id: x.tool_use_id, text: x.text, isError: x.isError ?? false })) }));
  return sha(jsonCanonical(rows));
}

function defaultGoal(messages) {
  return messages.filter((message) => message.role === 'user' && message.text.trim().length > 0 &&
    (message.toolResults ?? []).length === 0).slice(-3).map((message) =>
    message.text.length <= 500 ? message.text : `${message.text.slice(0, 499)}…`).join('\n');
}

function stripPrivate(message) {
  const { role, text, toolUses, toolResults } = message;
  return { role, text, toolUses, ...(toolResults?.length ? { toolResults } : {}) };
}

function publicMessages(messages) { return messages.map(stripPrivate); }

function countsFor(messages, recent) {
  const callIds = new Set();
  const resultIds = new Set();
  const callRows = [];
  let resultOccurrences = 0;
  messages.forEach((message, index) => {
    for (const call of message.toolUses) {
      if (callIds.has(call.tool_use_id)) continue;
      callIds.add(call.tool_use_id);
      callRows.push({ id: call.tool_use_id, callIndex: index });
    }
    for (const result of message.toolResults ?? []) { resultOccurrences += 1; resultIds.add(result.tool_use_id); }
  });
  const paired = callRows.filter((call) => resultIds.has(call.id)).map((call) => {
    const resultIndex = messages.findIndex((m) => (m.toolResults ?? []).some((r) => r.tool_use_id === call.id));
    return { ...call, resultIndex, pinned: call.callIndex === 0 || call.callIndex >= messages.length - recent ||
      resultIndex === 0 || resultIndex >= messages.length - recent };
  });
  const missingResults = callRows.filter((call) => !resultIds.has(call.id)).length;
  const orphanResults = [...resultIds].filter((id) => !callIds.has(id)).length;
  const duplicateCallIds = messages.reduce((n, m) => n + m.toolUses.length, 0) - callIds.size;
  const duplicateResultIds = resultOccurrences - resultIds.size;
  const candidates = paired.filter((call) => !call.pinned).length;
  return { messages: messages.length, userMessages: messages.filter((m) => m.role === 'user').length,
    assistantMessages: messages.filter((m) => m.role === 'assistant').length,
    toolCalls: callIds.size, toolResults: resultIds.size, pairedToolCalls: paired.length,
    unmatchedToolCalls: missingResults, orphanToolResults: orphanResults, duplicateToolUseIds: duplicateCallIds,
    duplicateToolResultIds: duplicateResultIds,
    candidateCalls: candidates, adapterHttpRequests: 2 * candidates };
}

function publicStream(group, messages, name, recent) {
  const counts = countsFor(messages, recent);
  const invalid = messages.reduce((n, m) => n + (m._errors?.length ?? 0), 0);
  const contentHash = messageFingerprint(messages);
  const normalized = { schema_version: 1, messages: publicMessages(messages) };
  const pairIssues = counts.unmatchedToolCalls + counts.orphanToolResults + counts.duplicateToolUseIds + counts.duplicateToolResultIds;
  const rejectionCodes = [...new Set(messages.flatMap((m) => m._errors ?? []))];
  if (counts.unmatchedToolCalls) rejectionCodes.push('unmatched_tool_calls');
  if (counts.orphanToolResults) rejectionCodes.push('orphan_tool_results');
  if (counts.duplicateToolUseIds) rejectionCodes.push('duplicate_tool_use_ids');
  if (counts.duplicateToolResultIds) rejectionCodes.push('duplicate_tool_result_ids');
  return {
    stream_id: `stream-${opaque(identityKey(group.identity))}`,
    artifact_name: name,
    source_files_sha256: [...new Set(messages.map((m) => m._location.sourceFileSha256))].sort(),
    source_rows_sha256: sha(messages.map((m) => `${m._location.sourceFileSha256}:${m._location.line}`).join('\n')),
    normalized_stream_sha256: sha(JSON.stringify(normalized)),
    text_and_tool_content_sha256: contentHash,
    counts,
    unsupported_or_integrity_issue_count: invalid,
    unsupported_or_integrity_error_codes: [...new Set(rejectionCodes)].sort(),
    eligible_for_execution: invalid === 0 && pairIssues === 0,
    cross_stream_parent_links: group.crossStreamParentLinks.length,
    cross_stream_parent_ids_sha256: group.crossStreamParentLinks.length ? sha(group.crossStreamParentLinks.join('\n')) : null,
    source_only_parent_links: group.sourceOnlyParentIds.length,
    source_only_parent_ids_sha256: group.sourceOnlyParentIds.length ? sha(group.sourceOnlyParentIds.join('\n')) : null,
    ambiguous_parent_links: group.ambiguousParentLinks.length,
    unresolved_parent_links: group.unresolvedParentIds.length,
    unresolved_parent_ids_sha256: group.unresolvedParentIds.length ? sha(group.unresolvedParentIds.join('\n')) : null,
    unresolved_parent_link_limit: 'No parent/child stream stitching is performed; cross-stream links and parent IDs absent from all loaded streams are reported separately.',
    normalized,
  };
}

function boundarySnapshots(group, boundaries, allMessages, recent) {
  const output = [];
  for (const boundary of boundaries ?? []) {
    const prefix = allMessages.filter((message) => compareLocation(message._location, boundary.location) < 0);
    const uuidList = boundary.preserved?.allUuids ?? boundary.preserved?.uuids ?? null;
    const mappedPreserved = Array.isArray(uuidList) ? uuidList.filter((id) => allMessages.some((m) => m._uuid === id)).length : null;
    const evidence = {
      boundary_uuid_sha256: boundary.uuid ? sha(boundary.uuid) : null,
      boundary_source_sha256: boundary.location.sourceFileSha256,
      boundary_line: boundary.location.line,
      prefix_message_count: prefix.length,
      preserved_uuid_count: Array.isArray(uuidList) ? uuidList.length : null,
      preserved_uuid_matches_in_prefix: Array.isArray(uuidList) ? uuidList.filter((id) => prefix.some((m) => m._uuid === id)).length : null,
      captured_metadata_map_count: mappedPreserved,
      input_snapshot_authenticity: 'source-order prefix approximation; transcript does not store the exact pre-compaction hook message array',
    };
    const counts = countsFor(prefix, recent);
    const parserIssues = prefix.reduce((sum, message) => sum + (message._errors?.length ?? 0), 0);
    const pairingIssues = counts.unmatchedToolCalls + counts.orphanToolResults + counts.duplicateToolUseIds + counts.duplicateToolResultIds;
    output.push({ boundary, prefix, counts, evidence });
    output[output.length - 1].eligibleForExecution = parserIssues === 0 && pairingIssues === 0;
    output[output.length - 1].parserIssueCount = parserIssues;
    output[output.length - 1].pairingIssueCount = pairingIssues;
  }
  return output;
}

async function writeNew(file, content) {
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, content, { flag: 'wx' });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { process.stdout.write(`${usage()}\n`); return 0; }
  const root = path.resolve(args.source);
  const receiptPath = path.resolve(args.receipt);
  const outDir = args.outputDir ? path.resolve(args.outputDir) : null;
  if (!path.isAbsolute(root) || isWithin(root, REPO_ROOT) || isWithin(receiptPath, REPO_ROOT) || (outDir && isWithin(outDir, REPO_ROOT))) {
    throw new Error('source_receipt_and_output_must_be_outside_repository');
  }
  if (args.prepare && path.resolve(outDir) === root) throw new Error('output_directory_must_differ_from_source');
  const files = await listJsonl(root);
  if (!files.length) throw new Error('no_raw_jsonl_sources');
  const { groups, boundaries, report } = await readSources(root, files);
  const streams = [];
  let boundaryCount = 0;
  let boundaryCandidates = 0;
  let boundaryRequests = 0;
  let boundarySupport = { sourceCaptured: 0, sourcePrefixBuilt: 0, exactPreCompactionArrayAvailable: 0 };
  for (const group of [...groups.values()].sort((a, b) => identityKey(a.identity).localeCompare(identityKey(b.identity), 'en'))) {
    const messages = group.messages;
    const streamId = `stream-${opaque(identityKey(group.identity))}`;
    const mainName = `${streamId}.json`;
    const normalized = publicStream(group, messages, mainName, args.preserveRecent);
    const { normalized: privateNormalized, ...publicRecord } = normalized;
    const boundaryRows = boundaries.get(identityKey(group.identity)) ?? [];
    const snapshots = args.boundaries ? boundarySnapshots(group, boundaryRows, messages, args.preserveRecent) : [];
    boundaryCount += snapshots.length;
    boundarySupport.sourceCaptured += boundaryRows.length;
    boundarySupport.sourcePrefixBuilt += snapshots.length;
    boundarySupport.exactPreCompactionArrayAvailable += 0;
    for (const snapshot of snapshots) {
      boundaryCandidates += snapshot.counts.candidateCalls;
      boundaryRequests += snapshot.counts.adapterHttpRequests;
    }
    streams.push({ ...publicRecord, prepared: args.prepare, boundaries: snapshots.map((snapshot, index) => ({
      boundary_id: `boundary-${opaque(`${streamId}:${snapshot.boundary.uuid || snapshot.boundary.location.line}`)}`,
      artifact_name: `${streamId}-boundary-${String(index + 1).padStart(3, '0')}.json`,
      counts: snapshot.counts,
      eligible_for_execution: snapshot.eligibleForExecution,
      parser_issue_count: snapshot.parserIssueCount,
      pairing_issue_count: snapshot.pairingIssueCount,
      evidence: snapshot.evidence,
      prefix_sha256: messageFingerprint(snapshot.prefix),
      run_id: randomUUID(),
      run_identity: { source_or_prefix_sha256: messageFingerprint(snapshot.prefix),
        upstream_package: 'fast-jev-compaction@0.4.1', model_digest: null,
        settings: { goal_sha256: sha(defaultGoal(snapshot.prefix)), keepThreshold: args.keepThreshold, preserveRecentMessages: args.preserveRecent,
          maxStateTokens: args.maxStateTokens, maxRequestTokens: args.maxRequestTokens,
          truncateHeadChars: args.truncateHeadChars, numCtx: 9216 } },
      run_identity_sha256: null,
    })) });
    for (const snapshot of streams[streams.length - 1].boundaries) snapshot.run_identity_sha256 = sha(jsonCanonical(snapshot.run_identity));
    streams[streams.length - 1].run_id = randomUUID();
    streams[streams.length - 1].run_identity = { source_or_prefix_sha256: publicRecord.normalized_stream_sha256,
      upstream_package: 'fast-jev-compaction@0.4.1', model_digest: null,
      settings: { goal_sha256: sha(defaultGoal(messages)), keepThreshold: args.keepThreshold, preserveRecentMessages: args.preserveRecent,
        maxStateTokens: args.maxStateTokens, maxRequestTokens: args.maxRequestTokens,
        truncateHeadChars: args.truncateHeadChars, numCtx: 9216 } };
    streams[streams.length - 1].run_identity_sha256 = sha(jsonCanonical(streams[streams.length - 1].run_identity));
    if (args.prepare) {
      await writeNew(path.join(outDir, mainName), `${JSON.stringify(privateNormalized)}\n`);
      for (const [index, snapshot] of snapshots.entries()) {
        const name = `${streamId}-boundary-${String(index + 1).padStart(3, '0')}.json`;
        await writeNew(path.join(outDir, name), `${JSON.stringify({ schema_version: 1, messages: publicMessages(snapshot.prefix) })}\n`);
      }
    }
  }
  const aggregate = streams.reduce((sum, row) => {
    for (const key of ['messages', 'userMessages', 'assistantMessages', 'toolCalls', 'toolResults', 'pairedToolCalls',
      'unmatchedToolCalls', 'orphanToolResults', 'duplicateToolUseIds', 'duplicateToolResultIds', 'candidateCalls', 'adapterHttpRequests']) {
      sum[key] = (sum[key] ?? 0) + row.counts[key];
    }
    sum.unsupportedOrIntegrityIssues += row.unsupported_or_integrity_issue_count;
    sum.unresolvedParentLinks += row.unresolved_parent_links;
    sum.crossStreamParentLinks += row.cross_stream_parent_links;
    sum.sourceOnlyParentLinks += row.source_only_parent_links;
    sum.ambiguousParentLinks += row.ambiguous_parent_links;
    return sum;
  }, { unsupportedOrIntegrityIssues: 0, unresolvedParentLinks: 0, crossStreamParentLinks: 0,
    sourceOnlyParentLinks: 0, ambiguousParentLinks: 0 });
  const receipt = {
    schema_version: 1,
    tool: 'fast-jev-compaction-corpus-planner',
    upstream_library: 'fast-jev-compaction@0.4.1',
    status: args.prepare ? 'prepared' : 'dry_run',
    inference_called: false,
    hosted_api_called: false,
    transcript_content_included: false,
    source_manifest_sha256: sha(report.sourceHashes.map((f) => `${f.path_sha256}:${f.sha256}:${f.bytes}`).sort().join('\n')),
    source_files: report.sourceFiles,
    source_bytes: report.sourceBytes,
    source_rows: report.sourceRows,
    malformed_rows: report.malformedRows,
    duplicate_rows_collapsed: report.duplicateRowsCollapsed,
    conflicting_duplicate_uuids: report.conflictingDuplicateUuids,
    source_file_hashes: report.sourceHashes.map(({ path_sha256, sha256, bytes }) => ({ path_sha256, sha256, bytes })),
    stream_count: streams.length,
    aggregate,
    boundaries: {
      source_captured: boundarySupport.sourceCaptured,
      source_order_prefixes_staged: boundarySupport.sourcePrefixBuilt,
      exact_pre_compaction_hook_arrays_available: boundarySupport.exactPreCompactionArrayAvailable,
      boundary_candidate_calls: boundaryCandidates,
      adapter_http_requests_if_executed: boundaryRequests,
      semantics: 'A boundary prefix uses only same-stream messages earlier in source-file order. It is not the exact pre-compaction hook array unless the source separately proves equivalence.',
    },
    parser_error_codes: report.errors,
    streams,
    parent_child_links: {
      cross_stream_parent_references: report.crossStreamParentLinks,
      unresolved_parent_links: report.unresolvedParentLinks,
      references_to_source_rows_not_in_compaction_messages: report.sourceOnlyParentLinks,
      references_with_multiple_source_stream_owners: report.ambiguousParentLinks,
      treatment: 'Root and sidechain streams are never merged. Cross-stream references, references to excluded raw rows, ambiguous owners, and references absent from all loaded streams are reported separately.',
    },
    run_configuration: { keepThreshold: args.keepThreshold, preserveRecentMessages: args.preserveRecent,
      maxStateTokens: args.maxStateTokens, maxRequestTokens: args.maxRequestTokens,
      truncateHeadChars: args.truncateHeadChars, numCtx: 9216, model_digest: null,
      note: 'Digest is unbound during offline preparation. Actual replay.mjs receipts bind the verified local digest and recompute identity.' },
    upstream_behavior_limits: [
      'The library judges paired tool_use/tool_result records only; it does not classify user-message relations or research readiness.',
      'Message.text concatenates text blocks in source order with no trim or separator. The upstream Message contract cannot preserve interleaving of text and tool blocks or non-text media.',
      'Thinking, redacted-thinking, and signature blocks are intentionally excluded; unsupported content blocks make their stream non-comparable and are reported by code/count.',
      'Library candidate pairing ignores unpaired calls/results, but this converter reports these and does not mark the stream valid for execution.',
      'The package uses estimated tokens, may abridge/collapse older state, and returns decisions for a compaction snapshot rather than a per-event walk-forward.',
      'OpenJev A/B top-token scores are uncalibrated and are not Jev confidence.',
    ],
  };
  if (args.prepare) {
    receipt.prepared_output_files = streams.reduce((sum, stream) => sum + 1 + stream.boundaries.length, 0);
    receipt.prepared_output_dir_sha256 = sha(outDir);
  }
  await writeNew(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ status: receipt.status, inference_called: false, transcript_content_included: false,
    source_manifest_sha256: receipt.source_manifest_sha256, source_files: receipt.source_files, stream_count: receipt.stream_count,
    aggregate, boundaries: receipt.boundaries, malformed_rows: report.malformedRows,
    conflicting_duplicate_uuids: report.conflictingDuplicateUuids, parser_error_codes: report.errors,
    receipt: receiptPath })}\n`);
  return 0;
}

main().then((code) => { process.exitCode = code; }).catch((error) => {
  const failure = String(error?.message ?? 'corpus_planner_failed').replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 120);
  process.stderr.write(`${JSON.stringify({ status: 'rejected', inference_called: false, transcript_content_included: false, failure })}\n`);
  process.exitCode = 2;
});

#!/usr/bin/env python3
"""Generate n8n workflow JSON files with correctly escaped JavaScript."""
import json
from pathlib import Path

OUT = Path(__file__).parent.parent / "workflows"

# ---------------------------------------------------------------------------
# Shared JS code blocks
# ---------------------------------------------------------------------------

FETCH_PARSE = r"""const { url, docType, entryDate, slug, documentId } = $input.item.json;

// Retry fetch with exponential backoff; treat 4xx as permanent error
let html = '';
let fetchError = null;
let errorType = null;
for (let attempt = 1; attempt <= 3; attempt++) {
  try {
    const raw = await this.helpers.httpRequest({ method: 'GET', url, timeout: 30000 });
    html = typeof raw === 'string' ? raw : Buffer.isBuffer(raw) ? raw.toString('utf8') : '';
    break;
  } catch (e) {
    fetchError = e;
    const status = e.response?.status;
    const isPermanent = status && status >= 400 && status < 500;
    errorType = isPermanent ? 'permanent' : 'transient';
    if (isPermanent || attempt === 3) break;
    await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt - 1)));
  }
}
if (fetchError) {
  return [{ json: { _fetchError: fetchError.message, _errorType: errorType, documentId, url, docType, entryDate, slug } }];
}
await new Promise(r => setTimeout(r, 1200));

// Skip abrogated laws — CSS class only; freetext "aufgehoben" has false positives in amendment laws
if (/<[^>]+class="[^"]*aufgehoben[^"]*"[^>]*>/i.test(html)) {
  console.log(`Skipping abrogated: ${slug}`);
  return [{ json: { _abrogated: true, documentId, url, docType, entryDate, slug } }];
}

const strip = s => s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

const titleM = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
const title = titleM ? strip(titleM[1]) : null;

let abbreviation = null;
const abbrM = html.match(/<dt[^>]*>\s*Abk.rzung\s*<\/dt>\s*<dd[^>]*>([^<]{1,60})<\/dd>/i)
           || html.match(/Abk.rzung[^<]*<[^>]+>([A-ZÄÖÜ][^<]{1,50})</i);
if (abbrM) abbreviation = abbrM[1].trim();

let enactmentDate = null;
const enactM = html.match(/<dt[^>]*>\s*Ausfertigungsdatum\s*<\/dt>\s*<dd[^>]*>\s*(\d{2}\.\d{2}\.\d{4})/i)
            || html.match(/Ausfertigungsdatum[\s\S]{0,200}?(\d{2}\.\d{2}\.\d{4})/i);
if (enactM) {
  const [d, mo, y] = enactM[1].split('.');
  enactmentDate = `${y}-${mo}-${d}`;
}

let lastAmendmentDate = null;
const amendM = html.match(/zuletzt\s+ge[äa]ndert[\s\S]{0,300}?(\d{2}\.\d{2}\.\d{4})/i)
            || html.match(/[Ll]etzte\s+[Ää]nderung[\s\S]{0,200}?(\d{2}\.\d{2}\.\d{4})/i);
if (amendM) {
  const [d, mo, y] = amendM[1].split('.');
  lastAmendmentDate = `${y}-${mo}-${d}`;
}

// Publication date from GV-Fundstelle (e.g. "GV. NRW. 2025 S. 1068 vom 15.08.2025")
let publicationDate = null;
const fundM = html.match(/Fundstelle[\s\S]{0,300}?(\d{2}\.\d{2}\.\d{4})/i);
if (fundM) {
  const [d, mo, y] = fundM[1].split('.');
  publicationDate = `${y}-${mo}-${d}`;
}

const typeMap = { gesetz: 'law', rechtsverordnung: 'regulation', bekanntmachung: 'announcement' };

const bodyM = html.match(/<main[^>]*>([\s\S]*?)<\/main>/i)
           || html.match(/<article[^>]*>([\s\S]*?)<\/article>/i);
const textContent = bodyM ? strip(bodyM[1]).slice(0, 2500) : strip(html).slice(0, 2500);

return [{
  json: {
    documentId, slug, docType, url, entryDate,
    title, abbreviation, enactmentDate, lastAmendmentDate, publicationDate,
    legalType: typeMap[docType] || 'law',
    textContent
  }
}];"""

# Kein GENERATE_SUMMARY-Code-Node mehr: Summary-Generierung laeuft jetzt ueber
# den nativen n8n HTTP-Request-Node mit Google-Gemini-Credential (googlePalmApi).
# Dieser Code-Node laeuft NACH dem HTTP-Request-Node und liest die Antwort aus.
EXTRACT_SUMMARY = r"""// $json = Gemini API Response
// Ursprungsdaten aus dem Fetch-Node per Item-Pairing wiederherstellen
const law = $('Fetch & Parse Law Page').item.json;
const summary = $json?.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || null;
return [{ json: { ...law, summary } }];"""

SEND_ALERT_BF = r"""const report = $input.item.json;
const errorRate = report.fetched > 0 ? report.errors / report.fetched : 0;
const webhookUrl = $vars.ALERT_WEBHOOK_URL || null;

if (errorRate > 0.1) {
  const msg = `[nrw_backfill] High error rate: ${(errorRate * 100).toFixed(1)}% (${report.errors}/${report.fetched}) runId=${report.runId}`;
  console.warn(msg);
  if (webhookUrl) {
    try {
      await this.helpers.httpRequest({
        method: 'POST',
        url: webhookUrl,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert: 'high_error_rate', workflow: 'nrw_backfill', errorRate: (errorRate * 100).toFixed(1) + '%', errors: report.errors, fetched: report.fetched, runId: report.runId })
      });
    } catch (e) {
      console.log(`Alert webhook failed: ${e.message}`);
    }
  }
}
return [$input.item];"""

SEND_ALERT_DAILY = r"""const report = $input.item.json;
const errorRate = report.fetched > 0 ? report.errors / report.fetched : 0;
const webhookUrl = $vars.ALERT_WEBHOOK_URL || null;

if (errorRate > 0.1) {
  const msg = `[nrw_daily] High error rate: ${(errorRate * 100).toFixed(1)}% (${report.errors}/${report.fetched}) runId=${report.runId}`;
  console.warn(msg);
  if (webhookUrl) {
    try {
      await this.helpers.httpRequest({
        method: 'POST',
        url: webhookUrl,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert: 'high_error_rate', workflow: 'nrw_daily', errorRate: (errorRate * 100).toFixed(1) + '%', errors: report.errors, fetched: report.fetched, runId: report.runId })
      });
    } catch (e) {
      console.log(`Alert webhook failed: ${e.message}`);
    }
  }
}
return [$input.item];"""

# ---------------------------------------------------------------------------
# Backfill-specific blocks
# ---------------------------------------------------------------------------

BF_FETCH_SITEMAPS = r"""const fs = require('fs');
const BASE = 'https://recht.nrw.de';
const DELAY_MS = 600;
const today = new Date().toISOString().split('T')[0];
const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
if (!fs.existsSync(resultsDir)) fs.mkdirSync(resultsDir, { recursive: true });

// Clean up orphaned accumulator files from aborted previous runs (older than 24h)
try {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  for (const f of fs.readdirSync(resultsDir).filter(f => f.startsWith('_acc_') && f.endsWith('.ndjson'))) {
    const fp = `${resultsDir}/${f}`;
    if (fs.statSync(fp).mtimeMs < cutoff) { fs.unlinkSync(fp); console.log(`Removed orphaned: ${f}`); }
  }
} catch (e) {}

// Resume checkpoint: skip already-processed slugs
const progressFile = `${resultsDir}/backfill_progress.txt`;
let processedSlugs = new Set();
if (fs.existsSync(progressFile)) {
  try {
    processedSlugs = new Set(fs.readFileSync(progressFile, 'utf8').split('\n').filter(Boolean));
    console.log(`Resuming backfill: ${processedSlugs.size} slugs already done`);
  } catch (e) {}
}

const ndjsonPath = `${resultsDir}/_backfill_active.ndjson`;
// Fresh start: remove stale accumulator if no resume checkpoint exists
if (!fs.existsSync(progressFile) && fs.existsSync(ndjsonPath)) {
  fs.unlinkSync(ndjsonPath);
  console.log('Removed stale backfill accumulator (fresh start)');
}

// Dynamically count sitemaps from index sitemap
let TOTAL = 47;
try {
  const indexRaw = await this.helpers.httpRequest({ method: 'GET', url: `${BASE}/sitemap.xml` });
  const indexXml = typeof indexRaw === 'string' ? indexRaw : Buffer.isBuffer(indexRaw) ? indexRaw.toString('utf8') : '';
  const m = indexXml.match(/<sitemap>/g);
  if (m) TOTAL = m.length;
} catch (e) {
  console.log(`Sitemap index fetch failed, using default ${TOTAL}: ${e.message}`);
}
console.log(`Fetching ${TOTAL} sitemaps`);

const bySlug = {};
let failedSitemaps = 0;
for (let i = 1; i <= TOTAL; i++) {
  const sUrl = `${BASE}/sitemap/page/${i}/sitemap.xml`;
  let xml = '';
  try {
    const raw = await this.helpers.httpRequest({ method: 'GET', url: sUrl });
    xml = typeof raw === 'string' ? raw : Buffer.isBuffer(raw) ? raw.toString('utf8') : '';
  } catch (e) {
    console.log(`Sitemap ${i} failed: ${e.message}`);
    failedSitemaps++;
    continue;
  }

  const blockRe = /<url>([\s\S]*?)<\/url>/g;
  let blk;
  while ((blk = blockRe.exec(xml)) !== null) {
    const locM = blk[1].match(/<loc>([^<]+)<\/loc>/);
    const lmodM = blk[1].match(/<lastmod>([^<]+)<\/lastmod>/);
    if (!locM) continue;
    const loc = locM[1].trim();
    if (!loc.includes('/lrgv/')) continue;
    const m = loc.match(/\/lrgv\/([^\/]+)\/(\d{8})-([^\/]+)\/?$/);
    if (!m) continue;
    const [, docType, dateStr, slug] = m;
    // URL date format is DDMMYYYY
    const entryDate = `${dateStr.slice(4,8)}-${dateStr.slice(2,4)}-${dateStr.slice(0,2)}`;
    if (entryDate > today) continue;
    if (processedSlugs.has(slug)) continue;
    if (!bySlug[slug] || bySlug[slug].entryDate < entryDate) {
      bySlug[slug] = { url: loc, lastmod: lmodM ? lmodM[1].trim() : null, docType, dateStr, entryDate, slug, documentId: slug };
    }
  }
  if (i < TOTAL) await new Promise(r => setTimeout(r, DELAY_MS));
}

if (failedSitemaps > TOTAL / 2) {
  throw new Error(`Sitemap fetch mostly failed: ${failedSitemaps}/${TOTAL} sitemaps unreachable — aborting backfill`);
}
const laws = Object.values(bySlug);
console.log(`Found ${laws.length} unique NRW laws (${processedSlugs.size} skipped from prior run)`);
return laws.map(l => ({ json: l }));"""

BF_BUILD_ENRICHED = r"""const fs = require('fs');

const item = $input.item.json;
const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
if (!fs.existsSync(resultsDir)) fs.mkdirSync(resultsDir, { recursive: true });
const ndjsonPath = `${resultsDir}/_backfill_active.ndjson`;
const progressFile = `${resultsDir}/backfill_progress.txt`;

// Write error record to NDJSON so it is counted in the final report
if (item._fetchError || item._abrogated) {
  const reason = item._abrogated ? 'abrogated'
    : (item._errorType === 'permanent' ? 'http_error_permanent' : 'http_error_transient');
  fs.appendFileSync(ndjsonPath, JSON.stringify({ _error: true, documentId: item.documentId, reason, message: item._fetchError || 'abrogated' }) + '\n', 'utf8');
  fs.appendFileSync(progressFile, item.documentId + '\n', 'utf8');
  return [{ json: { _skipped: true, documentId: item.documentId, reason } }];
}

const legalAct = {
  document_id: item.documentId,
  jurisdiction: 'de_nw',
  entity_type: 'legal_act',
  is_in_force: true,
  language: 'de',
  url: item.url || null,
  canonical_source_url: item.url || null,
  fallback_text_url: null,
  title: item.title || null,
  title_short: item.abbreviation || null,
  abbreviation: item.abbreviation || null,
  type: item.legalType || null,
  summary: item.summary || null,
  entry_into_force_date: item.entryDate || null,
  enactment_date: item.enactmentDate || null,
  last_amendment_date: item.lastAmendmentDate || null,
  validity_date: null,
  publication_date: item.publicationDate || null
};

const enrichedDoc = { legal_act: legalAct, legal_act_relations: [] };
fs.appendFileSync(ndjsonPath, JSON.stringify(enrichedDoc) + '\n', 'utf8');

// Update resume checkpoint (append-only: O(1) per document)
fs.appendFileSync(progressFile, item.documentId + '\n', 'utf8');

return [{ json: { _ok: true, documentId: item.documentId } }];"""

BF_COMPILE = r"""const fs = require('fs');

const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
const ndjsonPath = `${resultsDir}/_backfill_active.ndjson`;

let documents = [];
let fetchErrors = 0;
let parseErrors = 0;
let enrichedCount = 0;
const errorReasonMap = {};

if (fs.existsSync(ndjsonPath)) {
  const lines = fs.readFileSync(ndjsonPath, 'utf8').split('\n').filter(l => l.trim());
  for (const line of lines) {
    try {
      const rec = JSON.parse(line);
      if (rec._error) {
        fetchErrors++;
        errorReasonMap[rec.reason] = (errorReasonMap[rec.reason] || 0) + 1;
      } else {
        documents.push(rec);
        if (rec.legal_act?.summary) enrichedCount++;
      }
    } catch (e) {
      parseErrors++;
    }
  }
  fs.unlinkSync(ndjsonPath);
}

// Delete progress file on successful completion
const progressFile = `${resultsDir}/backfill_progress.txt`;
if (fs.existsSync(progressFile)) fs.unlinkSync(progressFile);

const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outFile = `${resultsDir}/backfill_${ts}.json`;
fs.writeFileSync(outFile, JSON.stringify(documents, null, 2), 'utf8');

const totalErrors = fetchErrors + parseErrors;
if (parseErrors > 0) errorReasonMap['parse_error'] = (errorReasonMap['parse_error'] || 0) + parseErrors;
const topErrorReasons = Object.entries(errorReasonMap)
  .map(([reason, count]) => ({ reason, count }))
  .sort((a, b) => b.count - a.count);

const report = {
  runId: `backfill_${ts}`,
  mode: 'backfill',
  fetched: documents.length + totalErrors,
  extracted: documents.length,
  enriched: enrichedCount,
  newDocuments: documents.length,
  updatedDocuments: 0,
  errors: totalErrors,
  topErrorReasons
};

const reportFile = `${resultsDir}/run_report_${ts}.json`;
fs.writeFileSync(reportFile, JSON.stringify(report, null, 2), 'utf8');

console.log(`Backfill complete: ${documents.length} docs, ${totalErrors} errors → ${outFile}`);
return [{ json: report }];"""

# ---------------------------------------------------------------------------
# Daily-specific blocks
# ---------------------------------------------------------------------------

DP_READ_CHECKPOINT = r"""const fs = require('fs');

const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
if (!fs.existsSync(resultsDir)) fs.mkdirSync(resultsDir, { recursive: true });

// Clean up orphaned accumulator files from aborted previous runs (older than 24h)
try {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  for (const f of fs.readdirSync(resultsDir).filter(f => f.startsWith('_acc_') && f.endsWith('.ndjson'))) {
    const fp = `${resultsDir}/${f}`;
    if (fs.statSync(fp).mtimeMs < cutoff) { fs.unlinkSync(fp); console.log(`Removed orphaned: ${f}`); }
  }
} catch (e) {}

const checkpointFile = `${resultsDir}/checkpoint.json`;

let lastRun;
if (fs.existsSync(checkpointFile)) {
  try {
    lastRun = JSON.parse(fs.readFileSync(checkpointFile, 'utf8')).lastRun;
  } catch (e) {
    lastRun = null;
  }
}

if (!lastRun) {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  lastRun = d.toISOString().split('T')[0];
}

console.log(`Daily pipeline starting. Checkpoint: ${lastRun}`);
return [{ json: { lastRun } }];"""

DP_FETCH_CHANGED = r"""const BASE = 'https://recht.nrw.de';
const DELAY_MS = 600;
const today = new Date().toISOString().split('T')[0];

const { lastRun } = $input.item.json;
const since = lastRun;

// Dynamically count sitemaps from index sitemap
let TOTAL = 47;
try {
  const indexRaw = await this.helpers.httpRequest({ method: 'GET', url: `${BASE}/sitemap.xml` });
  const indexXml = typeof indexRaw === 'string' ? indexRaw : Buffer.isBuffer(indexRaw) ? indexRaw.toString('utf8') : '';
  const m = indexXml.match(/<sitemap>/g);
  if (m) TOTAL = m.length;
} catch (e) {
  console.log(`Sitemap index fetch failed, using default ${TOTAL}: ${e.message}`);
}

// 2-day buffer for clock skew
const buffer = new Date(since);
buffer.setDate(buffer.getDate() - 2);
const sinceWithBuffer = buffer.toISOString().split('T')[0];

const bySlug = {};
let failedSitemaps = 0;
for (let i = 1; i <= TOTAL; i++) {
  const sUrl = `${BASE}/sitemap/page/${i}/sitemap.xml`;
  let xml = '';
  try {
    const raw = await this.helpers.httpRequest({ method: 'GET', url: sUrl });
    xml = typeof raw === 'string' ? raw : Buffer.isBuffer(raw) ? raw.toString('utf8') : '';
  } catch (e) {
    console.log(`Sitemap ${i} failed: ${e.message}`);
    failedSitemaps++;
    continue;
  }

  const blockRe = /<url>([\s\S]*?)<\/url>/g;
  let blk;
  while ((blk = blockRe.exec(xml)) !== null) {
    const locM = blk[1].match(/<loc>([^<]+)<\/loc>/);
    const lmodM = blk[1].match(/<lastmod>([^<]+)<\/lastmod>/);
    if (!locM) continue;
    const loc = locM[1].trim();
    if (!loc.includes('/lrgv/')) continue;
    const lastmod = lmodM ? lmodM[1].trim().slice(0, 10) : null;
    if (!lastmod || lastmod < sinceWithBuffer) continue;
    const m = loc.match(/\/lrgv\/([^\/]+)\/(\d{8})-([^\/]+)\/?$/);
    if (!m) continue;
    const [, docType, dateStr, slug] = m;
    // URL date format is DDMMYYYY
    const entryDate = `${dateStr.slice(4,8)}-${dateStr.slice(2,4)}-${dateStr.slice(0,2)}`;
    if (entryDate > today) continue;
    if (!bySlug[slug] || bySlug[slug].entryDate < entryDate) {
      bySlug[slug] = { url: loc, lastmod, docType, dateStr, entryDate, slug, documentId: slug };
    }
  }

  if (i < TOTAL) await new Promise(r => setTimeout(r, DELAY_MS));
}

if (failedSitemaps > TOTAL / 2) {
  throw new Error(`Sitemap fetch mostly failed: ${failedSitemaps}/${TOTAL} sitemaps unreachable — aborting daily run`);
}
const laws = Object.values(bySlug);
console.log(`Changed since ${since}: ${laws.length} unique laws`);

if (laws.length === 0) {
  return [{ json: { _noChanges: true } }];
}
return laws.map(l => ({ json: l }));"""

DP_BUILD_ENRICHED = r"""const fs = require('fs');

const item = $input.item.json;
const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
if (!fs.existsSync(resultsDir)) fs.mkdirSync(resultsDir, { recursive: true });
const runId = ($execution && $execution.id) ? $execution.id : 'daily';
const ndjsonPath = `${resultsDir}/_acc_${runId}.ndjson`;

if (item._fetchError || item._abrogated) {
  const reason = item._abrogated ? 'abrogated'
    : (item._errorType === 'permanent' ? 'http_error_permanent' : 'http_error_transient');
  fs.appendFileSync(ndjsonPath, JSON.stringify({ _error: true, documentId: item.documentId, reason, message: item._fetchError || 'abrogated' }) + '\n', 'utf8');
  return [{ json: { _skipped: true, documentId: item.documentId, reason } }];
}

const legalAct = {
  document_id: item.documentId,
  jurisdiction: 'de_nw',
  entity_type: 'legal_act',
  is_in_force: true,
  language: 'de',
  url: item.url || null,
  canonical_source_url: item.url || null,
  fallback_text_url: null,
  title: item.title || null,
  title_short: item.abbreviation || null,
  abbreviation: item.abbreviation || null,
  type: item.legalType || null,
  summary: item.summary || null,
  entry_into_force_date: item.entryDate || null,
  enactment_date: item.enactmentDate || null,
  last_amendment_date: item.lastAmendmentDate || null,
  validity_date: null,
  publication_date: item.publicationDate || null
};

const enrichedDoc = { legal_act: legalAct, legal_act_relations: [] };
fs.appendFileSync(ndjsonPath, JSON.stringify(enrichedDoc) + '\n', 'utf8');

return [{ json: { _ok: true, documentId: item.documentId } }];"""

DP_SAVE_RESULTS = r"""const fs = require('fs');

const path = require('path');
const resultsDir = $vars.RESULTS_DIR || path.join(require('os').homedir(), '.n8n', 'nrw-results');
if (!fs.existsSync(resultsDir)) fs.mkdirSync(resultsDir, { recursive: true });

const runId = ($execution && $execution.id) ? $execution.id : 'daily';
const ndjsonPath = `${resultsDir}/_acc_${runId}.ndjson`;

let documents = [];
let fetchErrors = 0;
let parseErrors = 0;
let enrichedCount = 0;
const errorReasonMap = {};

if (fs.existsSync(ndjsonPath)) {
  const lines = fs.readFileSync(ndjsonPath, 'utf8').split('\n').filter(l => l.trim());
  for (const line of lines) {
    try {
      const rec = JSON.parse(line);
      if (rec._error) {
        fetchErrors++;
        errorReasonMap[rec.reason] = (errorReasonMap[rec.reason] || 0) + 1;
      } else {
        documents.push(rec);
        if (rec.legal_act?.summary) enrichedCount++;
      }
    } catch (e) {
      parseErrors++;
    }
  }
  fs.unlinkSync(ndjsonPath);
}

const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const today = new Date().toISOString().split('T')[0];
const outFile = `${resultsDir}/daily_${ts}.json`;
fs.writeFileSync(outFile, JSON.stringify(documents, null, 2), 'utf8');

// Re-read checkpoint to get lastRun for new-vs-updated heuristic
const checkpointFile = `${resultsDir}/checkpoint.json`;
let lastRun = null;
if (fs.existsSync(checkpointFile)) {
  try { lastRun = JSON.parse(fs.readFileSync(checkpointFile, 'utf8')).lastRun; } catch (e) {}
}
// Heuristic: "new" = entry_into_force_date >= lastRun. Cannot distinguish first-seen from re-fetched
// without an external store. A law active since 2010 with a 2026 fassung counts as new.
const newDocs = documents.filter(d => lastRun && d.legal_act?.entry_into_force_date >= lastRun).length;
const updatedDocs = documents.length - newDocs;

const totalErrors = fetchErrors + parseErrors;
if (parseErrors > 0) errorReasonMap['parse_error'] = (errorReasonMap['parse_error'] || 0) + parseErrors;
const topErrorReasons = Object.entries(errorReasonMap)
  .map(([reason, count]) => ({ reason, count }))
  .sort((a, b) => b.count - a.count);

const report = {
  runId: `daily_${ts}`,
  mode: 'daily',
  fetched: documents.length + totalErrors,
  extracted: documents.length,
  enriched: enrichedCount,
  newDocuments: newDocs,
  updatedDocuments: updatedDocs,
  errors: totalErrors,
  topErrorReasons
};

const reportFile = `${resultsDir}/run_report_${ts}.json`;
fs.writeFileSync(reportFile, JSON.stringify(report, null, 2), 'utf8');

// Update checkpoint only when error rate is acceptable; skip on catastrophic runs so next run retries
const errorRate = (documents.length + totalErrors) > 0 ? totalErrors / (documents.length + totalErrors) : 0;
if (errorRate < 0.5) {
  fs.writeFileSync(checkpointFile, JSON.stringify({ lastRun: today }), 'utf8');
} else {
  console.warn(`Error rate ${(errorRate * 100).toFixed(1)}% > 50%: checkpoint NOT updated, next run will retry`);
}

console.log(`Daily complete: ${documents.length} docs, ${totalErrors} errors, checkpoint → ${today}`);
return [{ json: report }];"""

# ---------------------------------------------------------------------------
# Error-Reporter-Workflow (n8n Error Trigger → Alert Webhook)
# Wird als errorWorkflow in beiden Haupt-Workflows referenziert.
# Import-Reihenfolge: nrw_error_reporter zuerst importieren, danach die anderen.
# ---------------------------------------------------------------------------

ERROR_REPORTER_JS = r"""const execution = $input.item.json;
const webhookUrl = $vars.ALERT_WEBHOOK_URL || null;

const workflowName = execution.workflow?.name || 'unknown';
const errorMessage = execution.execution?.error?.message || 'Unknown error';
const lastNode = execution.execution?.lastNodeExecuted || 'unknown';
const executionId = execution.execution?.id || 'unknown';

const msg = `[${workflowName}] CRASH at "${lastNode}": ${errorMessage}`;
console.error(msg);

if (webhookUrl) {
  try {
    await this.helpers.httpRequest({
      method: 'POST',
      url: webhookUrl,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert: 'workflow_crash', workflow: workflowName, error: errorMessage, lastNode, executionId })
    });
  } catch (e) {
    console.log(`Alert webhook failed: ${e.message}`);
  }
}
return [$input.item];"""

# ---------------------------------------------------------------------------
# Build workflow dicts
# ---------------------------------------------------------------------------

def node(id_, name, type_, version, position, params):
    return {"parameters": params, "id": id_, "name": name, "type": type_,
            "typeVersion": version, "position": position}

def code_node(id_, name, pos, js, mode="runOnce"):
    params = {"jsCode": js}
    if mode != "runOnce":
        params["mode"] = mode
    return node(id_, name, "n8n-nodes-base.code", 2, pos, params)

def if_node(id_, name, pos, condition):
    """IF-Node (typeVersion 1) mit einer Boolean-Bedingung."""
    return node(id_, name, "n8n-nodes-base.if", 1, pos, {
        "conditions": {"boolean": [{"value1": condition, "value2": True}]}
    })

def gemini_http_node(id_, name, pos):
    """HTTP-Request-Node fuer Gemini 2.5 Flash via googlePalmApi-Credential.
    Prompt: 3-Satz-Zusammenfassung (Gegenstand, Adressaten, Rechtsfolgen).
    Nach Import Credential im Node manuell verknuepfen."""
    body_expr = (
        '={{ {\n'
        '  "system_instruction": {\n'
        '    "parts": [{ "text": "Du bist ein juristischer Assistent zur Datenextraktion.'
        ' Fasse den Text in GENAU 3 vollständigen, inhaltlich dichten Sätzen zusammen.'
        ' Satz 1: Was wird geregelt (Gegenstand und Zweck)?'
        ' Satz 2: Für wen gilt es (Beteiligte, Adressaten, Geltungsbereich)?'
        ' Satz 3: Welche konkreten Rechtsfolgen oder Maßnahmen werden festgelegt?'
        ' Jeder Satz muss mindestens 20 Wörter lang sein.'
        ' Antworte AUSSCHLIESSLICH mit dem unformatierten, reinen Text der Zusammenfassung.'
        ' Verwende KEIN JSON, KEIN Markdown und KEINE Einleitungsfloskeln." }]\n'
        '  },\n'
        '  "contents": [{\n'
        '    "parts": [{ "text": "Titel: " + ($json.title || "Kein Titel") +'
        ' "\\n\\nText:\\n" + ($json.textContent || "Kein Text vorhanden").slice(0, 3000) }]\n'
        '  }],\n'
        '  "generationConfig": {\n'
        '    "maxOutputTokens": 2500,\n'
        '    "temperature": 0.1\n'
        '  }\n'
        '} }}'
    )
    n = node(id_, name, "n8n-nodes-base.httpRequest", 4.2, pos, {
        "method": "POST",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googlePalmApi",
        "sendHeaders": True,
        "headerParameters": {"parameters": []},
        "sendBody": True,
        "contentType": "raw",
        "rawContentType": "application/json",
        "body": body_expr,
        "options": {}
    })
    n["retryOnFail"] = True
    n["maxTries"] = 5
    n["waitBetweenTries"] = 5000
    n["credentials"] = {"googlePalmApi": {"name": "Google Gemini(PaLM) Api account"}}
    return n


# Enrich-Abschnitt (Backfill):
#   Fetch & Parse → Should Enrich? (IF)
#     TRUE  → Call Gemini (HTTP Request, googlePalmApi Credential) → Extract Summary (Code)
#     FALSE → direkt zu Build EnrichedDocument (summary bleibt null)
# Beide Pfade landen in Build EnrichedDocument.
BACKFILL = {
    "name": "nrw_backfill",
    "nodes": [
        node("bf000001-0000-0000-0000-000000000001", "Start",
             "n8n-nodes-base.manualTrigger", 1, [180, 400], {}),
        code_node("bf000001-0000-0000-0000-000000000002", "Fetch All Sitemap URLs",
                  [420, 400], BF_FETCH_SITEMAPS),
        node("bf000001-0000-0000-0000-000000000003", "Loop: Process Laws",
             "n8n-nodes-base.splitInBatches", 3, [660, 400],
             {"batchSize": 1, "options": {}}),
        code_node("bf000001-0000-0000-0000-000000000004", "Fetch & Parse Law Page",
                  [900, 240], FETCH_PARSE),
        # IF: TRUE = hat Inhalt → Claude aufrufen; FALSE = Fehler/abrogated → direkt weiter
        if_node("bf000001-0000-0000-0000-000000000009", "Should Enrich?", [1140, 240],
                "={{ !$json._fetchError && !$json._abrogated && !!$json.textContent }}"),
        gemini_http_node("bf000001-0000-0000-0000-000000000010", "Call Gemini", [1380, 80]),
        code_node("bf000001-0000-0000-0000-000000000011", "Extract Summary",
                  [1620, 80], EXTRACT_SUMMARY),
        code_node("bf000001-0000-0000-0000-000000000006", "Build EnrichedDocument",
                  [1860, 240], BF_BUILD_ENRICHED),
        code_node("bf000001-0000-0000-0000-000000000007", "Compile & Save Results",
                  [900, 580], BF_COMPILE, mode="runOnceForAllItems"),
        code_node("bf000001-0000-0000-0000-000000000008", "Send Alert",
                  [1140, 580], SEND_ALERT_BF),
    ],
    "connections": {
        "Start":                  {"main": [[{"node": "Fetch All Sitemap URLs",   "type": "main", "index": 0}]]},
        "Fetch All Sitemap URLs": {"main": [[{"node": "Loop: Process Laws",        "type": "main", "index": 0}]]},
        "Loop: Process Laws":     {"main": [
            [{"node": "Compile & Save Results", "type": "main", "index": 0}],
            [{"node": "Fetch & Parse Law Page", "type": "main", "index": 0}],
        ]},
        "Fetch & Parse Law Page": {"main": [[{"node": "Should Enrich?",           "type": "main", "index": 0}]]},
        "Should Enrich?":         {"main": [
            [{"node": "Call Gemini",            "type": "main", "index": 0}],  # TRUE
            [{"node": "Build EnrichedDocument", "type": "main", "index": 0}],  # FALSE
        ]},
        "Call Gemini":            {"main": [[{"node": "Extract Summary",           "type": "main", "index": 0}]]},
        "Extract Summary":        {"main": [[{"node": "Build EnrichedDocument",    "type": "main", "index": 0}]]},
        "Build EnrichedDocument": {"main": [[{"node": "Loop: Process Laws",        "type": "main", "index": 0}]]},
        "Compile & Save Results": {"main": [[{"node": "Send Alert",                "type": "main", "index": 0}]]},
    },
    "active": False,
    "settings": {"executionOrder": "v1", "errorWorkflow": "nrw-error-reporter"},
    "versionId": "00000000-0000-0000-0000-000000000001",
    "meta": {"templateCredsSetupCompleted": False},
    "id": "nrw-backfill",
}

# IF node: true branch (output 0) = has changes → Loop; false branch (output 1) = no changes → Save
IF_NO_CHANGES = {
    "parameters": {
        "conditions": {
            "boolean": [{"value1": "={{ !$json._noChanges }}", "value2": True}]
        }
    },
    "id": "dp000002-0000-0000-0000-000000000009",
    "name": "No Changes?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 1,
    "position": [900, 400],
}

DAILY = {
    "name": "nrw_daily_pipeline",
    "nodes": [
        node("dp000002-0000-0000-0000-000000000001", "Daily 06:00",
             "n8n-nodes-base.scheduleTrigger", 1.2, [180, 400],
             {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * *"}]}}),
        code_node("dp000002-0000-0000-0000-000000000002", "Read Checkpoint",
                  [420, 400], DP_READ_CHECKPOINT),
        code_node("dp000002-0000-0000-0000-000000000003", "Fetch Changed Law URLs",
                  [660, 400], DP_FETCH_CHANGED),
        IF_NO_CHANGES,
        node("dp000002-0000-0000-0000-000000000004", "Loop: Process Laws",
             "n8n-nodes-base.splitInBatches", 3, [1140, 400],
             {"batchSize": 1, "options": {}}),
        code_node("dp000002-0000-0000-0000-000000000005", "Fetch & Parse Law Page",
                  [1380, 240], FETCH_PARSE),
        if_node("dp000002-0000-0000-0000-000000000011", "Should Enrich?", [1620, 240],
                "={{ !$json._fetchError && !$json._abrogated && !!$json.textContent }}"),
        gemini_http_node("dp000002-0000-0000-0000-000000000012", "Call Gemini", [1860, 80]),
        code_node("dp000002-0000-0000-0000-000000000013", "Extract Summary",
                  [2100, 80], EXTRACT_SUMMARY),
        code_node("dp000002-0000-0000-0000-000000000007", "Build EnrichedDocument",
                  [2340, 240], DP_BUILD_ENRICHED),
        code_node("dp000002-0000-0000-0000-000000000008", "Save Results & Update Checkpoint",
                  [1380, 580], DP_SAVE_RESULTS, mode="runOnceForAllItems"),
        code_node("dp000002-0000-0000-0000-000000000010", "Send Alert",
                  [1620, 580], SEND_ALERT_DAILY),
    ],
    "connections": {
        "Daily 06:00":            {"main": [[{"node": "Read Checkpoint",                    "type": "main", "index": 0}]]},
        "Read Checkpoint":        {"main": [[{"node": "Fetch Changed Law URLs",             "type": "main", "index": 0}]]},
        "Fetch Changed Law URLs": {"main": [[{"node": "No Changes?",                        "type": "main", "index": 0}]]},
        "No Changes?":            {"main": [
            [{"node": "Loop: Process Laws",               "type": "main", "index": 0}],
            [{"node": "Save Results & Update Checkpoint", "type": "main", "index": 0}],
        ]},
        "Loop: Process Laws":     {"main": [
            [{"node": "Save Results & Update Checkpoint", "type": "main", "index": 0}],
            [{"node": "Fetch & Parse Law Page",           "type": "main", "index": 0}],
        ]},
        "Fetch & Parse Law Page": {"main": [[{"node": "Should Enrich?",                    "type": "main", "index": 0}]]},
        "Should Enrich?":         {"main": [
            [{"node": "Call Gemini",            "type": "main", "index": 0}],  # TRUE
            [{"node": "Build EnrichedDocument", "type": "main", "index": 0}],  # FALSE
        ]},
        "Call Gemini":            {"main": [[{"node": "Extract Summary",                    "type": "main", "index": 0}]]},
        "Extract Summary":        {"main": [[{"node": "Build EnrichedDocument",             "type": "main", "index": 0}]]},
        "Build EnrichedDocument": {"main": [[{"node": "Loop: Process Laws",                 "type": "main", "index": 0}]]},
        "Save Results & Update Checkpoint": {"main": [[{"node": "Send Alert",               "type": "main", "index": 0}]]},
    },
    "active": False,
    "settings": {"executionOrder": "v1", "errorWorkflow": "nrw-error-reporter"},
    "versionId": "00000000-0000-0000-0000-000000000002",
    "meta": {"templateCredsSetupCompleted": False},
    "id": "nrw-daily-pipeline",
}

ERROR_REPORTER = {
    "name": "nrw_error_reporter",
    "nodes": [
        node("er000003-0000-0000-0000-000000000001", "Error Trigger",
             "n8n-nodes-base.errorTrigger", 1, [180, 400], {}),
        code_node("er000003-0000-0000-0000-000000000002", "Send Crash Alert",
                  [420, 400], ERROR_REPORTER_JS),
    ],
    "connections": {
        "Error Trigger": {"main": [[{"node": "Send Crash Alert", "type": "main", "index": 0}]]},
    },
    "active": True,
    "settings": {"executionOrder": "v1"},
    "versionId": "00000000-0000-0000-0000-000000000003",
    "meta": {"templateCredsSetupCompleted": False},
    "id": "nrw-error-reporter",
}

if __name__ == "__main__":
    for name, workflow in [
        ("nrw_error_reporter", ERROR_REPORTER),
        ("nrw_backfill", BACKFILL),
        ("nrw_daily_pipeline", DAILY),
    ]:
        out = OUT / f"{name}.json"
        out.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Written {out}")

#!/usr/bin/env node
// Drive agent-browser to capture one Rigzone posting and pre-parse the
// deterministic fields, so the skill spends model tokens only on the
// semantic mapping.
//
// stdout is ALWAYS a single JSON line the model can parse:
//   success: {"ok":true,"id":"...","out":"tmp/rigzone-read/<id>.json","url":"..."}
//   failure: {"ok":false,"reason":"<code>","message":"...","url":"..."}
// Human-readable progress goes to stderr. Exit code is 0 on success, non-zero
// on failure — but the model should key off the stdout "ok" flag + "reason".
//
// Failure reasons: invalid_url, no_posting_id, browser_error,
//                  requirement_empty, unexpected_error
//
// Usage: node extract.js "<rigzone posting url>" [--keep-open]

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const url = process.argv[2] || null;
const keepOpen = process.argv.includes('--keep-open');

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}
function fail(reason, message) {
  emit({ ok: false, reason, message: message || null, url });
  process.exit(1);
}
function log(msg) {
  process.stderr.write(`[extract] ${msg}\n`);
}

if (!url || !/rigzone\.com\/oil\/jobs\/postings\//.test(url)) {
  fail('invalid_url', 'Pass a rigzone.com/oil/jobs/postings/... URL as the first argument.');
}

const idExternal = (url.match(/postings\/(\d+)/) || [])[1];
if (!idExternal) {
  fail('no_posting_id', 'Could not parse the numeric posting id from the URL path.');
}

const projectRoot = path.resolve(__dirname, '..', '..', '..');
const outDir = path.join(projectRoot, 'tmp', 'rigzone-read');

// Wrap every agent-browser call so a CLI/browser failure surfaces as a
// structured browser_error on stdout instead of an uncaught stack trace.
function ab(args, input) {
  try {
    return execFileSync('agent-browser', args, {
      input: input || undefined,
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (e) {
    const detail = (e.stderr || e.stdout || e.message || '').toString().trim().slice(0, 400);
    fail('browser_error', `agent-browser ${args[0]} failed: ${detail}`);
  }
}

// agent-browser eval returns its result as a JSON-quoted string
// (e.g. "\"{...}\"" ). Unwrap until we reach the page value.
function evalPage(js) {
  const raw = (ab(['eval', '--stdin'], js) || '').trim();
  let v = raw;
  for (let i = 0; i < 3; i++) {
    if (typeof v === 'string') {
      const t = v.trim();
      if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith('{') && t.endsWith('}'))) {
        try { v = JSON.parse(t); continue; } catch { /* fallthrough */ }
      }
    }
    break;
  }
  return v;
}

// One page-side extractor: pulls the header + #requirement (active tab,
// no click) and regex-parses the label:value meta lines in-page.
const EXTRACTOR = `
(() => {
  const clean = s => (s || "").replace(/[ \\t]+/g, " ").replace(/\\n{3,}/g, "\\n\\n").trim();
  const req = document.querySelector('#requirement') || document.querySelector('.tab-content');
  const reqText = req ? req.innerText : "";
  const header = (document.querySelector('main') || document.body).innerText || "";
  const body = document.body.innerText || "";
  const h1 = document.querySelector('h1');
  const grab = (label, src) => {
    const m = (src || "").match(new RegExp(label + "\\\\s*:\\\\s*([^\\n]+)", "i"));
    return m ? m[1].trim() : null;
  };
  const scope = reqText + "\\n" + header;
  const posted = (body.match(/Posted\\s*:\\s*([A-Za-z]{3}\\.?\\s+\\d{1,2},\\s*\\d{4})/i) || [])[1] || null;
  return JSON.stringify({
    reqLen: (reqText || "").length,
    title: h1 ? h1.innerText.trim() : (document.title || "").split(" - ")[0].trim(),
    pageTitle: document.title || null,
    meta: {
      company: grab("Company", scope),
      skills: grab("Skills", scope),
      experience: grab("Experience", scope),
      education: grab("Education", scope),
      location: grab("Location", scope),
      employment_type: grab("Employment Type", scope),
      posted_date: posted,
      requisition_number: grab("Requisition Number", scope),
      experience_level: grab("Experience Level", scope),
      job_family: grab("Job Family", scope),
      product_service_line: grab("Product Service Line", scope),
      full_part_time: grab("Full[\\\\s/]*Part Time", scope),
    },
    rawRequirement: clean(reqText),
    rawHeader: clean(header),
  });
})();
`;

function slug(s) {
  return (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

log(`opening ${url}`);
ab(['open', url]);
ab(['wait', '--load', 'networkidle']);

// The #requirement tab is active by default but its content renders a beat
// after networkidle. Poll until it is populated (same timing glitch as the
// scrape skill), up to ~6s.
let data = null;
for (let attempt = 1; attempt <= 8; attempt++) {
  data = evalPage(EXTRACTOR);
  if (data && typeof data === 'object' && data.reqLen > 300) break;
  log(`#requirement not ready (len=${data && data.reqLen}), retry ${attempt}`);
  ab(['wait', '800']);
}

if (!keepOpen) ab(['close']);

if (!data || typeof data !== 'object' || !data.rawRequirement || data.reqLen <= 300) {
  fail('requirement_empty',
    `#requirement never populated (len=${data && data.reqLen}). The description is missing — do not write a file; retry or inspect the page.`);
}

const titleSlug = slug(data.title);
const filename = `back/data/raw/${idExternal}-${titleSlug}.md`;

const result = {
  id_external: idExternal,
  source_url: url,
  filename,
  title: data.title,
  title_slug: titleSlug,
  page_title: data.pageTitle,
  meta: data.meta,
  raw_requirement: data.rawRequirement,
  raw_header: data.rawHeader,
};

let outPath;
try {
  fs.mkdirSync(outDir, { recursive: true });
  outPath = path.join(outDir, `${idExternal}.json`);
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
} catch (e) {
  fail('unexpected_error', `Failed to write intermediate JSON: ${e.message}`);
}

const m = data.meta;
log(`OK id=${idExternal} title="${data.title}" reqLen=${data.reqLen}`);
log(`meta: company=${m.company} location=${m.location} experience=${m.experience} employment_type=${m.employment_type} posted=${m.posted_date}`);
emit({ ok: true, id: idExternal, out: path.relative(projectRoot, outPath), url });

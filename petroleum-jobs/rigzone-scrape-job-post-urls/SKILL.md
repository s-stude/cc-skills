---
name: rigzone-scrape-job-post-urls
description: Use when the user wants to collect Rigzone job posting detail URLs from the search listing pages (rigzone.com/oil/jobs/search) and append them to the petroleum-jobs pending queue. Triggers on requests like "scrape rigzone job urls", "grab the job post links from rigzone search", "get pending posts from rigzone", "collect rigzone posting urls", or any ask to gather the listing-page links that feed the downstream read-one-post step. Walks N search pages (asks how many, defaults to the first 3), extracts the deduped posting URLs, and appends them to back/data/raw/pending-posts.md.
---

# Rigzone — Scrape Job Post URLs

## Overview

The Rigzone search listing (`rigzone.com/oil/jobs/search/`) is paginated. Each page lists ~20 jobs, and every job links to a detail page under `/oil/jobs/postings/`. This skill walks a chosen number of listing pages, collects those detail URLs, and appends them to `back/data/raw/pending-posts.md` — the queue that the `rigzone-read-one-post` step later consumes one URL at a time.

A URL must be appended to the pending queue only if it hasn't already been processed. `back/data/raw/processed/posts.md` is the log of URLs that have already been read and normalized — never re-queue a posting that appears there.

Two details make this reliable:

- Each posting is linked **twice** on a listing page — once as the canonical `?s=` form (e.g. `...postings/1289512_Associate_Metal_Fabricator...?s=8`) and once as a trailing-slash duplicate. Keep only the `?s=` form so the queue matches what the read-one-post skill expects and there's one entry per job.
- `agent-browser eval` reuses its JS scope across calls, so a bare `const links = ...` throws `Identifier already declared` on the second page. Always wrap extraction in an IIFE (`(() => { ... })()`).
- **`wait --load networkidle` is not enough on its own.** The first `eval` right after `open` + `wait --load networkidle` sometimes returns an empty string even though the page has a full ~20 postings — the listing links land in the DOM a beat after network idle. Confirm with `agent-browser get count 'a[href*="/oil/jobs/postings/"]'` (a real page shows ~40, i.e. two link forms per job) and **re-run the extraction eval once** if the first pass comes back empty. Do not treat a single empty result as end-of-pages (see Step 2).
- `agent-browser eval` returns its result as a **JSON-quoted string** (e.g. `"url1\nurl2\n..."` with escaped `\n`), not raw newlines. If you capture per-page output to a file, `JSON.parse` it before splitting on `\n`.

Use the `agent-browser` skill for browsing (load its core guide first: `agent-browser skills get core`). Rigzone renders fine headless.

## Step 1 — Decide how many pages to scan

Before scraping, settle the page count:

- If the user gave a number ("scan 5 pages", "just page 1", "pages 2–4"), use it.
- Otherwise **default to the first 3 pages** and tell the user that's what you're doing (e.g. "Scanning the first 3 search pages — say a number if you want more or fewer.").

Page URLs follow `https://www.rigzone.com/oil/jobs/search/?page=N` (page 1 is `?page=1`, or the bare `/search/`). Scan pages in order.

## Step 2 — For each page, open and extract

Open the page, wait for network idle, then extract with the IIFE below. It selects every posting link, keeps only the `?s=` canonical form, and dedupes within the page:

```bash
agent-browser open "https://www.rigzone.com/oil/jobs/search/?page=1"
agent-browser wait --load networkidle

cat <<'EOF' | agent-browser eval --stdin
(() => {
  const a = Array.from(document.querySelectorAll('a[href*="/oil/jobs/postings/"]'));
  const q = a.map(x => x.href).filter(h => h.includes("?s="));
  return [...new Set(q)].join("\n");
})();
EOF
```

Repeat for each page number (`?page=2`, `?page=3`, ...). Collect the URLs from every page into one list. When walking many pages, run them in **small batches (~3 pages per shell call)** — a single loop over 10 pages can exceed the 2-minute Bash timeout partway through.

If a page returns **zero** posting URLs, **re-run the extraction eval once** before concluding anything — an empty first pass is usually the load-timing glitch (see the "not enough on its own" note above), not an empty page. Check `agent-browser get count 'a[href*="/oil/jobs/postings/"]'`: if it reports ~40 links, the page has jobs and you just extracted too early. Only after a genuine second empty result (and a zero count) should you treat it as running past the last page (or a block) — stop there and note how many pages actually yielded results.

## Step 3 — Dedupe and append

Before writing, dedupe the combined list three ways so the queue stays clean. Match on the **posting id** (the numeric prefix in the path, e.g. `1289512`) throughout — it's stable against query-string differences (`?s=` values, trailing slashes):

1. Across the pages you just scanned (a job can occasionally appear on more than one page).
2. Against what's already in `back/data/raw/pending-posts.md` — don't re-append a URL that's already queued.
3. Against `back/data/raw/processed/posts.md` — drop any URL whose posting id already appears there. These have already been read/normalized downstream, so re-queuing them would reprocess duplicates.

Read both `pending-posts.md` and `processed/posts.md` first, build the set of known posting ids from them, and keep only scraped URLs whose id is in neither set. Append the surviving URLs, one per line, to `back/data/raw/pending-posts.md` (either file may not exist yet or may be empty — treat a missing file as an empty id set; create/append to pending, never overwrite existing lines).

Close the browser when done: `agent-browser close`.

## Step 4 — Report

Tell the user, per page and in total: how many URLs were found, how many were new, how many were skipped as already-pending or already-processed, and the final line count of `pending-posts.md`. Then offer to continue with the next pages.

## Notes

- One URL per line, no headers or bullets — the file is a plain queue that downstream tooling reads line by line.
- Keep the `?s=` query string intact; it's part of the canonical URL the read-one-post skill opens.
- If extraction returns the trailing-slash duplicates only (no `?s=` links), the page markup may have shifted — re-check the selector against a fresh `agent-browser snapshot -i -u` before assuming the page is empty.

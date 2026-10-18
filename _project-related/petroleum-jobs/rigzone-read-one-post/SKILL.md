---
name: rigzone-read-one-post
description: Use when the user wants to load a single Rigzone job posting (a rigzone.com/oil/jobs/postings/... URL) and save it as a structured markdown file in the petroleum-jobs project. Triggers on requests like "open this rigzone job and save it", "scrape this rigzone posting to md", "read one rigzone post", or when handed a Rigzone job URL to capture. Handles the tab-hidden description, the fixed field set, and the URL-slug filename so the raw file is ready for the job-post normalize step.
---

# Rigzone — Read One Post

## Overview

Rigzone job postings load with the full description inside a **Requirements & Summary** tab. That tab is active by default, but its content (`#requirement` / `.tab-content`) renders a beat *after* network idle, so a naive extract right on load comes back empty. This skill captures one posting completely and writes it as a markdown file with YAML frontmatter into `back/data/raw/`, ready for the `rigzone-normalize-job-post-to-json` step downstream.

To keep token cost low, the **browser capture and all deterministic parsing run in a script** — `scripts/extract.js`. Its browser output never enters the model context; it emits one compact JSON with the mechanical fields pre-filled. You (the model) then do only the semantic work — splitting the prose into sections and judging the `n/a` fields — and write the file. There is **no** snapshot-and-click-by-ref step anymore; the script reads the already-active tab directly (the old `.job-description` selector is stale — the content lives in `#requirement`).

## Workflow

### 1. Run the extract script

```bash
node skills/rigzone-read-one-post/scripts/extract.js "<url>"
```

The script opens the posting, polls until `#requirement` is populated (handling the render-timing glitch), regex-parses the deterministic fields, and writes `tmp/rigzone-read/<id>.json`. Progress goes to stderr; **stdout is always a single JSON line** — parse it and branch on `ok`:

```json
{"ok": true,  "id": "1288151", "out": "tmp/rigzone-read/1288151.json", "url": "…"}
{"ok": false, "reason": "requirement_empty", "message": "…", "url": "…"}
```

- **`ok: true`** — read the JSON at `out` and continue.
- **`ok: false`** — the posting was **not** captured; do not write a markdown file. React to `reason`:
  - `requirement_empty` — the description never rendered. Re-run once; if it still fails, the page markup may have shifted — inspect with `agent-browser`.
  - `browser_error` — the browser/CLI failed (`message` has the detail). Check the session, then re-run.
  - `invalid_url` / `no_posting_id` — the URL is wrong; fix it before retrying.

  Whatever the reason, that URL stays unread — leave it in the queue, skip it, or retry; never fabricate a file from a failed run.

For a batch, loop the script per URL (add `--keep-open` to reuse the browser session across posts and close it yourself at the end with `agent-browser close`).

### 2. Read the intermediate JSON

`tmp/rigzone-read/<id>.json` has this shape:

```json
{
  "id_external": "1288151",
  "source_url": "…",
  "filename": "back/data/raw/1288151-service-delivery-coordinator.md",
  "title": "Service Delivery Coordinator",
  "title_slug": "service-delivery-coordinator",
  "page_title": "Service Delivery Coordinator - Muscat",
  "meta": {
    "company": "Baker Hughes", "skills": "Coil Tubing",
    "experience": "10 + Years", "education": "Bachelors/3-5 yr Degree",
    "location": "Muscat, Oman", "employment_type": null, "posted_date": "Jul 08, 2026",
    "requisition_number": null, "experience_level": null,
    "job_family": null, "product_service_line": null, "full_part_time": null
  },
  "raw_requirement": "…full tab prose…",
  "raw_header": "…header block…"
}
```

### 3. Map to the frontmatter fields

Frontmatter field set (this exact set — the normalize step expects it):

`id_external`, `title`, `title_slug`, `description`, `company`, `location`, `skills`, `experience`, `education`, `employment_type`, `posted_date`, `salary`, `department`, `seniority_level`, `certifications`, `responsibilities`, `qualifications`, `benefits`, `industry`

**Come straight from the JSON (no model work — copy them):**

- `id_external`, `title_slug`, `source_url`, and the output `filename`.
- `company`, `location`, `skills`, `experience`, `education`, `posted_date` — from `meta`.
- `employment_type` — `meta.employment_type` if set, else `n/a`.
- `department` — `meta.job_family` (+ `meta.product_service_line` if present), else `n/a`.
- `seniority_level` — `meta.experience_level`, else `n/a`.

Not every posting carries the Job-Details block (Requisition Number, Experience Level, Job Family, PSL) — those `meta` fields are often `null`. Null → `n/a`, never guessed.

**Need your judgment (the reason this stays a model step):**

- `title` — usually `meta`/JSON `title` verbatim, but strip any trailing location/marketing suffix (`page_title` shows the location Rigzone appends).
- `description` — the summary paragraph + one-line role summary, distilled from the top of `raw_requirement`.
- `responsibilities` — the duties, as a bullet list. In `raw_requirement` these run together as sentences (employer-specific markers like "you will be responsible for…", "Job Duties") — split them into clean bullets.
- `qualifications` — the requirement lines (education/experience) plus any EEO statement, from the "To be successful…" / "Qualifications" region.
- `benefits` — real benefit content (health cover, life insurance, financial/dev programs) from the "Working for you" / "Own Your Career" prose. If none, `n/a`.
- `salary` — only a concrete figure or range. "Competitive and commensurate with experience" is **not** a salary → `n/a`.
- `certifications` — only if explicitly required in the text; otherwise `n/a`.
- `industry` — infer from context; default `Oil and Gas (Upstream Energy)` unless the posting says otherwise.

**Any field with no data in the posting → `n/a`** (never guess or leave blank). Firm rule: downstream code distinguishes "absent" from "empty", and a fabricated value is worse than an honest `n/a`.

### 4. Write the file

Use the `filename` the JSON gives you (`back/data/raw/<id_external>-<title-slug>.md`), e.g. `back/data/raw/1288151-service-delivery-coordinator.md`.

## Output Template

Use this exact structure:

```markdown
---
id_external: 1289335
title: Field Service Quality Coordinator
title_slug: field-service-quality-coordinator
company: Halliburton
location: Negara Brunei, Brunei Darussalam
skills: Field Service Tech
experience: 5 + Years
education: High School/Secondary
employment_type: Full Time Salaried Employee
posted_date: Jul 08, 2026
salary: n/a
department: Operations (Wireline and Perforating)
seniority_level: Experienced Hire
certifications: n/a
industry: Oil and Gas (Upstream Energy)
source_url: https://www.rigzone.com/oil/jobs/postings/1289335_field_service_quality_coordinator?s=8
---

# Field Service Quality Coordinator

## Description

<summary paragraph + role summary>

## Responsibilities

- <job duty>
- <job duty>

## Qualifications

- <requirement / EEO line>

## Benefits

- <benefit>

## Additional Details

- **Full Location:** <street address line, if present>
- **Requisition Number:** <number>
- **Experience Level:** <level>
- **Job Family:** <family>
- **Product Service Line:** <PSL>
- **Full Time / Part Time:** <value>
- **Compensation:** <compensation line>
```

Keep `source_url` in the frontmatter so the raw file is traceable back to its posting. In **Additional Details**, list only the items the posting actually carries; drop rows whose `meta` value is `null`.

## Notes

- The script owns the browser and the render-timing wait — don't re-implement open/wait/click by hand. If you need to eyeball the live page, use `agent-browser` directly, but the file's content should come from the script's JSON.
- One posting per JSON. The script overwrites `tmp/rigzone-read/<id>.json` each run, so a re-run is safe.
- If `raw_requirement` looks truncated or is missing the duties/qualifications prose, treat it like an `ok: false`: don't write a half-empty file.

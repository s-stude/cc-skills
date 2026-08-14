---
name: rigzone-normalize-job-post-to-json
description: Use when converting a scraped Rigzone job-post markdown file (back/data/raw/<id>-<slug>.md, produced by the rigzone-read-one-post skill) into a normalized jobposts JSON file (back/data/jobposts/job_<uid>.json). Covers the full pipeline — mechanical field derivation (uid, slugs, location parsing, employment/industry mapping, meta dates) plus content normalization (title cleanup, description summarizing, benefits filtering, salary and certification enrichment). Use whenever a raw Rigzone md needs to become a display-ready JSON job post, or the user says "normalize the raw post", "turn this md into a job post json", or "process back/data/raw".
---

# Rigzone — Normalize Job Post to JSON

## Overview

The `rigzone-read-one-post` skill drops raw postings into `back/data/raw/<id>-<slug>.md` as YAML frontmatter plus prose sections. This skill turns each one into the richer, display-ready JSON at `back/data/jobposts/job_<uid>.json`.

Two layers of work, split by nature:

1. **Mechanical layer — a bundled script does it.** Frontmatter parsing, slugs, `location_structure`, `employment_type_iso`, the `industry` taxonomy object, `meta` dates, and a stable `uid` are all deterministic. `scripts/md_to_json.py` writes a correct JSON skeleton so no run reinvents this and no two runs disagree.
2. **Judgment layer — you do it.** The raw md carries Rigzone's marketing boilerplate, EEO paragraphs, and empty salary/certification fields. Applying editorial judgment — what's a real benefit vs. a skill, what belongs in the description vs. duplicated elsewhere, which certifications the role implies — is what you add on top by editing the JSON the script produced.

Do the script step first, then read the JSON back and refine it. Never hand-build the JSON from scratch — you'll drift from the schema.

## Step 0 — Run the converter

```bash
python3 skills/rigzone-normalize-job-post-to-json/scripts/md_to_json.py <path-to-md>
# or a whole directory:
python3 skills/rigzone-normalize-job-post-to-json/scripts/md_to_json.py back/data/raw/
```

It prints the path(s) it wrote. The `uid` is a stable hash of the Rigzone `id_external`, so re-running on the same posting overwrites the same file rather than creating a duplicate — which also means: **run the script before you refine, not after, or you'll wipe your edits.**

For a batch, split the written files into ~10 groups and refine them with parallel agents (see the bottom of this file). For one or two files, just do it inline.

## Step 1 — Normalize the title

**Fields:** `title`, `title_slug`

Target a clean, readable title under ~60 characters, `Role Name - Location` only when the location is short and adds value. Rigzone titles are usually clean already, but watch for:

| Problem | Example | Fix |
|---------|---------|-----|
| Gender notation | `(m/f/d)`, `(M/F)` | Remove entirely |
| Internal abbreviations | `Svc Spec`, `Field Prof-DD`, `Svc Coord` | Expand to full words |
| Location as prefix | `Brazil - RJ: UX Researcher` | Flip to `UX Researcher - Rio de Janeiro` |
| ALL CAPS | `OPERATIONS ENGINEER` | Convert to title case |
| Requisition codes | `Accountant (Job# 206394)` | Remove the code |
| Internal level codes | `Svc Spec III-GBA` | Decode from context → `Service Specialist III - Nigeria` |

If you change `title`, update `title_slug` to match: lowercase, non-alphanumerics collapsed to single hyphens.

## Step 2 — Summarize the description

**Field:** `description`

Aim for a 2–5 sentence intro that gives *unique* context about the role — not a repeat of other fields. Rigzone descriptions almost always open with recruiter marketing that you should cut.

Cut:
- Company boilerplate ("We are looking for the right people…", "one of the world's largest providers…", Halliburton/Vestas mission statements, DEIB and recruitment-fraud paragraphs).
- Anything already living in `responsibilities`, `qualifications`, or `benefits`.
- Artifacts: `$TOO_LONG(...)` wrappers, raw `<li>` tags, "Job Duties:" / "Overview:" labels, "Not extracted…".

Keep (and if it's buried elsewhere, move it here): specific project/facility/site names, shift schedules, rotation patterns, travel %, contract duration, start dates, sign-on-bonus mechanics, "talent pool posting" caveats.

For the Field Service Quality Coordinator example, that means dropping the "We are looking for the right people…" paragraph and keeping the real one-line summary about driving service-quality excellence — then adding a sentence of specific context if the posting offers any.

Leave the description alone if it's already a clean, specific, non-redundant intro under ~300 characters.

## Step 3 — Enrich the structured fields

**Fields:** `certifications`, `responsibilities`, `qualifications`, `benefits`

The script copies these over from the md verbatim. Refine each:

**certifications** — Professional credentials the role clearly requires. Rigzone leaves this `[]` far too often; infer from the role when the requirement is obvious, otherwise leave `[]` (never invent a specific cert the posting doesn't imply). **First fix the splitter damage:** the script tokenizes on `&`, `,`, `;`, `/`, and " and ", so a single credential like `Basic Fire Fighter 1 & 2 (NFPA 1001)` arrives shredded into `["Basic Fire Fighter 1", "2 (NFPA 1001)"]` — re-merge these back into one entry before enriching (the same corruption can hit `skills`). Common by role:
- Offshore / oil & gas field: BOSIET, HUET, H2S Alive, IWCF, IADC WellSharp, OPITO
- HSE: NEBOSH IGC, IOSH, ISO 45001 Lead Auditor, OSHA 30-Hour
- Inspection / QA: CSWIP, API 510/570/653, ASNT NDT Level II/III, ISO 9001 Lead Auditor
- Engineering: PE license, PMP, API certifications, IChemE
- Wind / energy transition: GWO BST, GWO BTT, GWO ART, LOTO, Fall Arrest

**responsibilities** — Action-verb bullets of day-to-day work. Rigzone's "Job Duties" map here cleanly; just make sure no qualification text leaked in.

**qualifications** — Education, years of experience, skills, domain expertise. **Remove the EEO paragraph** the script carried in from the md (the "Equal Opportunity Employer… without regard to race, color, religion…" boilerplate is not a qualification).

**benefits** — ACTUAL employment benefits only:
- ✅ Health/dental/vision, 401k/pension, PTO, sign-on bonus, relocation, housing allowance, tuition reimbursement, performance bonus
- ❌ Technical skills, certifications, job duties, EEO statements
- Rigzone's "Own Your Career" prose ("Leadership and competency development", "Competitive compensation plans", "Health benefits"…) is acceptable but generic — keep it, and if the posting names a concrete perk (tax-free salary, flights, end-of-service gratuity for expat/Gulf roles; collective agreements like IG Metall for German roles), add it.
- If `benefits` is `[]` and the posting genuinely lists none, leave it `[]`. **Watch for the `["n/a"]` artifact:** when an md section body is literally `n/a`, the script's bullet parser doesn't apply the na-check and emits `["n/a"]` instead of `[]` — normalize it to `[]`. This can hit any section-derived list (`responsibilities`, `qualifications`, `benefits`), not just benefits.

## Step 4 — Extract salary

**Field:** `salary`

Rigzone almost always says *"Compensation is competitive and commensurate with experience"* — that is **not** a salary, so leave `salary` as `""`. Only populate it with a concrete figure or a genuinely descriptive package.

Scan `description`, `benefits`, `title`, and the md's "Additional Details → Compensation" line for a real number. Write the result as a complete phrase:
- `"$23 per hour"`
- `"$27.43 - $33.43 per hour; $2,500 USD sign-on bonus"`
- `"$57,600 - $86,400 per year"`
- `"Competitive tax-free salary with housing, transport, and annual airfare allowance"` (only when the posting actually describes such a package)

Combine components when both exist (`"$X per hour; $Y sign-on bonus"`). Never fabricate — no info anywhere → `""`.

## Step 5 — Sanity-check the derived fields

The script's mechanical guesses are usually right but a few are heuristic — glance at them and fix in the JSON if wrong:

- **`industry`** — mapped from the md's industry string by keyword. Rigzone's default `Oil and Gas (Upstream Energy)` maps to `upstream`. If the role is clearly oilfield-services, downstream, midstream, or energy-transition, correct the `{title, slug}` pair (valid slugs: `upstream`, `oilfield-services`, `downstream`, `midstream`, `trading-marketing`, `offshore`, `energy-transition`). **The company is often the fastest tell:** Halliburton (including its Landmark Software & Services division), SLB/Schlumberger, Baker Hughes, Weatherford, and NOV are `oilfield-services` regardless of the default `Upstream Energy` string — even for their non-field roles (marketing, HR, software), since the employer is a service company, not an operator. **Power / utility / renewable operators map to `energy-transition`, but the script's keyword map mis-defaults several of their industry strings to `oilfield-services` (not just `upstream`) — verify these by hand.** NextEra Energy and its subsidiaries (Florida Power & Light, NextEra Energy Resources, Duane Arnold) are `energy-transition` across all roles — nuclear, wind, solar, grid, and their corporate IT/PM/HR jobs. Industry strings like `Nuclear Power Generation`, `Electric Utility (Power Generation)`, and `Renewable Energy (...)` all belong in `energy-transition`. **Offshore vs. upstream:** an offshore operator whose posting centers on offshore platform/production work (e.g. GOM Administration's Gulf of America production operators, 14/14 rotations) is `offshore`, not the default `upstream`.
- **`location_structure`** — parsed by splitting on commas. Two-part locations become `{city, null, country}`; check that a `State, Country` didn't get mislabeled as `city`. The md's "Full Location" line in Additional Details is the ground truth if you need to correct it. Watch for these parser artifacts: a country-only posting duplicated as `Country, Country` (e.g. `Saudi Arabia, Saudi Arabia`) makes the country the `city` — set `city` to `null`; a `Negara <Country>` token means "Nation of …" and is not a city (the real city, e.g. Seria, is elsewhere in the Full Location line); and a mangled 2-letter state like `Warsaw, Ma, Poland` should be dropped to `null` (or expanded from the Full Location) rather than kept. When you correct `location_structure`, also rewrite the flat `location` string to match (drop bogus tokens, use the real city/state).
- **`is_remote_job`** — defaults to `false`. Set `true` only if the posting says remote/work-from-home.
- **`employment_type_iso`** — `FULL_TIME` / `CONTRACTOR` / `CONTRACT` / `INTERN` / `PART_TIME`, derived from `employment_type`. Verify it matches.

Leave `apply_url` as `null` and the `meta` block as-is unless you have a reason to change them.

## Writing back

Edit the JSON the script wrote (via Edit/Write), preserving every field and the schema shape exactly. Only touch a field you're deliberately changing. Do not add or remove top-level keys.

## After normalizing — regenerate the derived data

The jobposts JSON files are the source of truth; several data files are derived from them by the backend build. After creating or changing posts, from `back/` run:

```bash
npm run on-build
```

This runs `scripts/on-build/`: it validates every post's required fields and auto-fills missing `title_slug`/`company_slug`, then rebuilds `back/data/jobs-per-industry-index.json` from each post's `industry.slug`, and regenerates the sitemap. **Do not hand-edit `jobs-per-industry-index.json`** — it is regenerated wholesale. If the validator reports errors, fix the offending post's JSON and re-run.

**`company` is a required field the validator rejects when empty.** When the md has `company: n/a`, the script writes `company: ""` (and `company_slug: "n-a"`), which fails validation with `missing required field "company"`. Don't invent an employer — set `company` to `"Confidential"` and `company_slug` to `"confidential"` (the standard placeholder for an undisclosed employer), then re-run.

The two lookup files this skill conforms to are hand-maintained source-of-truth config, not outputs: `back/data/industry.json` (valid `{title, slug}` pairs — the validator rejects any `industry.slug` not listed here) and `back/data/employmentTypeIso.json` (the allowed `employment_type_iso` values). If you add a new industry or ISO value, edit those files and mirror the change in `scripts/md_to_json.py`.

## Agent prompt template (batch)

When fanning out over many raw files, split the script-written JSON paths into ~10 groups and tell each agent:

1. Read the assigned `job_<uid>.json` files (the script already wrote them) and their source md in `back/data/raw/`.
2. Apply Steps 1–5 above, editing each JSON in place.
3. Preserve every other field and the schema shape exactly; add/remove no top-level keys.
4. Do NOT re-run the converter script (it would overwrite refinements) and do NOT write ad-hoc mutation code — edit the JSON files directly.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Refining first, then running the script | Run the script FIRST — it overwrites the file |
| Leaving the EEO paragraph in `qualifications` | Remove it; it's boilerplate, not a qualification |
| Keeping recruiter marketing in `description` | Cut it; keep only unique role context |
| Putting skills/certs in `benefits` | Benefits are real perks only |
| Filling `salary` from "competitive and commensurate" | That's not a salary → `""` |
| Inventing certifications | Only add credentials the role clearly requires |
| Hand-building the JSON | Always start from the script's skeleton |
| Editing `title` but not `title_slug` | Update the slug whenever the title changes |
| Leaving a split multi-part cert (`Basic Fire Fighter 1` + `2 (NFPA 1001)`) | Re-merge into one credential — the script split it on `&`/`,` |
| Leaving `["n/a"]` in a list field | Normalize the section artifact to `[]` |
| Leaving a Halliburton/SLB/Baker Hughes role as `upstream` | Service companies are `oilfield-services`, even for non-field roles |
| Leaving a NextEra / power-utility / nuclear / renewable role as `oilfield-services` | Power & utility operators are `energy-transition` (the script mis-defaults these) |
| Leaving `company: ""` (from `company: n/a`) | Validator rejects empty company → set to `Confidential` / `confidential` |
| Keeping a parser location artifact (`Saudi Arabia, Saudi Arabia`, `Negara Brunei`, `Warsaw, Ma`) | Null the bogus token; use the Full Location line; sync the flat `location` string too |

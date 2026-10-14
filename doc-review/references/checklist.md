# Documentation review checklist

Work through every category. Not each item applies to every doc; the point is to not
forget a whole class of problem.

## 1. Correctness against the code

The doc is only as good as its match with reality. Verify rather than trust.

- Commands and scripts: does `npm run x` / `make y` / `./scripts/z` exist with that
  name, and do the flags shown exist? Check `package.json`, `Makefile`, the script.
- File and directory paths mentioned in prose or code blocks exist at those paths.
- Function, class, module, table, column, endpoint, route, event and queue names exist
  and are spelled as in the code.
- Config keys, env vars and defaults match the config loader / `.env.example`.
- Described behavior (ordering, retries, limits, state machines, error handling)
  matches the implementation. Spot-check the claims that matter most to a reader.
- Versions (runtime, database, dependencies) match manifests and lockfiles.
- Numbers presented as current (counts, thresholds, timings) match their source, or
  are clearly labelled as a historical measurement.

## 2. Broken references

- Relative links and `#anchors` that don't resolve (use `scripts/check_links.py`).
- Links to files that were deleted, renamed or moved — the `STALE` section of
  `scripts/diff_scope.py` covers the whole repo, including code comments, scripts,
  tests and READMEs next to code. It matches paths, so also search for prose that
  names the old location without a path.
- Links whose target exists but no longer contains what the link text promises.
- References by name rather than link ("see the ingestion spec") whose target is
  ambiguous or gone.
- Section numbers cited in text ("see §3.2") that no longer match the headings.

## 3. Conflicts

- Two docs stating different facts, steps, defaults or ownership for the same thing.
- A doc contradicting itself (summary vs detail section, table vs prose).
- Doc vs code comment vs README-next-to-code disagreement.
- Plan/task status contradictions: a task checked done while its plan is still in the
  open plans area, or a "completed" plan whose tasks are unchecked.
- For each conflict decide which side is authoritative (usually the code, then any doc
  the project names as source of truth) and propose fixing the other.

## 4. Gaps (missing data)

- New features, modules, config, env vars, scripts or migrations in the code or diff
  that no doc mentions.
- Missing prerequisites, setup steps, required permissions, or order of operations.
- Missing failure modes / recovery steps for operational docs.
- Index or map docs (ARCHITECTURE, docs README, TOC) that don't list a doc that now
  exists.
- Undefined terms or acronyms on first use; unexplained placeholders (`TODO`, `TBD`,
  `???`, `<fill in>`).
- Project doc rules not followed (e.g. required update of an architecture doc, moving
  finished plans to a completed folder).

## 5. Excess

- Content duplicated across docs that should link to one canonical place instead —
  duplication is where drift comes from.
- Implementation detail that belongs in code comments or will rot quickly (line-level
  walkthroughs, pasted code that already diverges from the real code).
- Historical narrative in a doc meant to describe current state (move to a changelog,
  ADR or completed plan).
- Sections that no longer apply to anything.
- Verbose passages that could be a table or a list without losing information.

## 6. Outdated files

- Docs describing removed features, old architecture, retired scripts.
- Plans/specs for work that is finished but not archived, or archived but not finished.
- Orphaned docs that nothing links to and that no index lists.
- "Last updated" stamps, version banners or status badges that are stale.

## 7. Structure and navigation

- Headings form a sensible hierarchy (no jumps from `#` to `###`), TOC matches headings.
- Entry points exist: a reader can find the doc from the docs index or README.
- Each doc has a clear purpose stated near the top.

## 8. Clarity and consistency

- Same concept, same name everywhere (not "job" in one doc and "task" in another for
  the same thing, unless defined).
- Consistent formatting of paths, commands, identifiers (code spans).
- Ambiguous pronouns or "it"/"this" that could refer to several things.
- Typos and grammar only when they change or obscure meaning, or are numerous.

## 9. Safety

- Secrets, tokens, internal hostnames or personal data committed in docs.
- Destructive commands (`rm -rf`, `DROP`, `reset --hard`, force pushes) without a
  warning or without saying which environment they target.

---
name: doc-review
description: Review documentation like code — a given doc file, a set of docs, or a git diff touching docs — and report issues, gaps, conflicts, missing or excessive content, broken links/anchors, stale references to code, and outdated files, each flagged Critical / Major / Minor with a proposed change and the reason for it. Use this whenever the user asks to review, audit, check, proofread, sanity-check or "code review" documentation, READMEs, ARCHITECTURE.md, specs, plans, requirements, task lists, runbooks or changelogs, or asks whether docs are up to date / consistent with the code / consistent with each other — even if they just say "review docs", "check this .md", "are the docs still right after this diff", or "review my doc changes before I commit".
---

# Documentation code review

Review documentation with the same rigor as a code review: find what is wrong, what is
missing, what contradicts something else, and what no longer matches the code. The
review comes first and is read-only. Proposed changes come with the reason behind each
one, and nothing is edited until the user says which findings to apply.

The reason for review-before-edit: doc fixes are often judgment calls (which of two
conflicting docs is the truth? is this section excessive or load-bearing?). The user
needs to see the whole picture and decide, rather than discover silent rewrites.

## 1. Determine the scope

Work out what to review from the request:

| Request | Scope |
|---|---|
| A path or several paths | Those files (a directory means every `.md` under it) |
| "my changes", "the diff", "before I commit" | `git diff HEAD` plus untracked docs from `git status --porcelain` |
| "staged" | `git diff --cached` |
| A branch, PR, commit or range | `git diff <base>...<head>` (default base: the main branch) |
| Nothing specific | Ask which doc or diff; don't guess at the whole repo |

For a diff, the reviewed set is every changed doc **plus** the docs and code that the
diff can break. Deleted, renamed or moved files are the most common source of broken
references. When the diff changes code, check whether the docs describing that code
were updated too — a code-only diff that leaves docs stale is a doc finding.

For any diff scope, start with the bundled scope script instead of raw `git diff`:

```bash
python3 <skill-dir>/scripts/diff_scope.py [--base REF | --cached | --range A..B] \
  --save <snapshot-dir>
```

It lists every changed file (doc or code, untracked included) and pairs deleted files
with their new copies, even when a move was done without `git mv` and shows up as a
deletion plus an untracked file. For each move it prints only the drift between old
and new copy, so a moved 3,000-line spec costs a few dozen lines instead of a full
deletion and re-read. It then searches the whole repo, code and tests included, for
references that still resolve to a deleted or moved path, and prints the `git diff`
command for the remaining changed files with the moves left out.

Put `<snapshot-dir>` in the session scratchpad (or the project's `./tmp` if there is
none), e.g. `<scratchpad>/doc-review/pass-1`. It saves the reviewed content so a later
re-review can show exactly what changed (section 7).

Also read the project's own documentation rules before judging anything: `CLAUDE.md`,
`AGENTS.md`, `CONTRIBUTING.md`, a docs index/README, or style guides. A project rule
(e.g. "keep ARCHITECTURE.md current", "move finished plans to plans/completed") turns a
matter of taste into a real finding.

## 2. Run the mechanical checks

Run the bundled link checker over the reviewed files. It resolves relative links,
`#anchors` (GitHub slug rules) and reference-style links, and reports what doesn't
resolve:

```bash
python3 <skill-dir>/scripts/check_links.py <file-or-dir> [...more] [--root <repo-root>]
```

Treat its output as leads, not verdicts: confirm each hit (a link may target a
generated file, a path outside the repo, or a heading produced by HTML). For a diff
scope, also run it on docs that link *into* the changed files, since renamed headings
break inbound anchors.

## 3. Review the content

How much to read depends on the scope, because contradictions hide in context but
long specs can swamp the review:

- **Path scope and new files:** read each doc in full.
- **Diff scope:** read every changed hunk with enough surrounding context to see the
  section it belongs to (`git diff -U10`, or open the section), plus moved files'
  drift as printed by the scope script. Open the rest of a file when a hunk makes a
  claim that other parts of the doc might contradict, such as a changed default,
  command, count or rule.

Then verify claims against the source of truth: open the code, config, scripts,
`package.json` (or equivalent), migrations and tests that the doc describes. A doc
claim you did not verify is not a finding either way; say so if something could not
be checked.

Work through `references/checklist.md` — it lists what to look for in each category
(correctness vs code, broken references, conflicts, gaps, excess, staleness, structure,
clarity) with concrete examples. Read it at the start of every review.

## 4. Assign severity

Rate by the harm to a reader who trusts the doc, not by the size of the edit:

- **Critical** — following the doc causes damage or a hard failure: wrong commands,
  destructive or unsafe instructions, wrong config/env/secret handling, contracts or
  APIs described incorrectly so integrations break, two docs giving opposite
  instructions for the same operation, a doc that the project marks as a source of
  truth being materially wrong.
- **Major** — the reader is misled or blocked, but not harmed: stale descriptions of
  behavior, missing required steps or prerequisites, broken links to important docs,
  a completed/obsolete plan still presented as open work (or vice versa), undocumented
  new feature or config, violated project doc rules, large duplicated content that
  already drifts.
- **Minor** — friction and polish: broken anchors to minor sections, inconsistent
  terminology or naming, unclear wording, formatting, small redundancy, typos, TOC out
  of order.

When unsure between two levels, pick the lower one and state what would raise it.

## 5. Write the report

Present findings first, grouped by severity, most severe first. Use this template:

```markdown
# Documentation review: <scope>

**Scope:** <files / diff range reviewed> · **Verified against:** <code, config, etc.>
**Result:** <N> critical · <N> major · <N> minor

## Critical

### C1. <short title>
- **Where:** `path/to/doc.md:42` (and any other locations involved)
- **Problem:** what is wrong, with the evidence (quote the doc, cite the code line).
- **Proposed change:** the concrete edit — replacement text, link target, section to
  add/remove, or file to move/delete.
- **Why:** the consequence of leaving it, and why this fix is the right one (e.g.
  which source is authoritative in a conflict).

## Major
### M1. ...

## Minor
### m1. ...

## Checked and fine
<one or two lines on what was verified and holds up, so the user knows coverage>

## Not verified
<claims that could not be checked and why — omit if none>

## Declined
<findings the user said to leave, one line each — omit if none>
```

Guidance for good findings:

- Cite exact locations (`file:line`) and quote the offending text, so the user can
  judge without reopening everything.
- Make proposed changes concrete enough to apply directly. "Clarify this section" is
  not a proposal; the rewritten sentence is.
- In a conflict, name both sides, say which one the code supports, and propose fixing
  the wrong one. If the code supports neither, say so.
- Merge duplicates: one finding for "12 links to the moved `plans/x/tasks.md`", listing
  the locations, not twelve findings.
- Skip pure style nitpicks the project clearly doesn't care about. A short report of
  real problems beats a long one padded with noise.

If there are no findings, say so plainly and still include "Checked and fine".

## 6. Apply only after approval

End the report by asking which findings to apply (e.g. "all", "critical and major",
"C1, M2, M3"). Then make exactly those edits, rerun the link checker on the touched
files, and summarize what changed. Findings the user rejects stay unapplied — don't
fold them into other edits.

A finding the user declines ("leave the backlog", "skip m4") is a decision, not an
open issue. On later passes in the same conversation, list it once under "Declined"
and don't raise it again as a finding unless the content it concerns has changed.

## 7. Re-review after fixes

When the user asks to review the same scope again ("again", "I fixed some", "re-check"),
review what changed rather than starting over. The first pass already verified the
untouched parts, and repeating that work costs time without finding anything new.

1. Rerun the scope script against the previous snapshot and save a new one:

   ```bash
   python3 <skill-dir>/scripts/diff_scope.py [same scope flags] \
     --since <snapshot-dir>/pass-1 --save <snapshot-dir>/pass-2
   ```

   The `SINCE LAST PASS` section lists files that changed, entered or left the scope
   since the last pass, with a diff of each change. If no snapshot exists (e.g. a new
   conversation), do a full review instead.
2. Rerun the link checker in full, since a fix in one file can break a link in another.
3. For each earlier finding, check whether the change fixes it. Review every new or
   changed hunk as in a first pass, because fixes can introduce new problems.
4. Report with this structure in place of the full template's findings sections:

```markdown
# Documentation review: <scope> (pass N)

**Changed since pass N-1:** <files> · **Result:** <N> fixed · <N> still open · <N> new

## Fixed since last pass
- **m2** — `file:line` <one line on how it was resolved>

## Still open
### m1. <title> (carried over)
<same fields as before, updated if the context moved>

## New
### M1. ...

## Declined
- **m4** — <one line>
```

Carried-over findings keep their original IDs so the user can track them across
passes; new findings continue the numbering.

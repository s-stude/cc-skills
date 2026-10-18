---
name: token-analysis
description: Audit past Claude Code work on a project, folder, branch, worktree or set of sessions. Reports tokens and cost per session, prompt, subagent, model, branch and day; tool calls and what agents spent time on (e2e and test runs, commits, restarts, waiting); wall-clock time for agents vs the human typing and reading; and git output (commits including killed and rebased ones, branches, worktrees, LOC added and removed). Built from the ~/.claude/projects transcripts and git history. Use it whenever the user asks how many tokens, how much money or how much time was spent, how many commits or lines were produced, asks for a usage, cost, productivity or effort report, wants to analyze past Claude sessions, transcripts or subagent usage, or asks "what did this project/branch cost", even if they don't name the skill.
---

# Token analysis

This skill produces one evidence-backed markdown report about past Claude Code work. The report covers tokens, cost, tools, time and git. Everything comes from two sources: the session transcripts under `~/.claude/projects/` and the git object store. Neither source needs network access, and nothing in the analyzed project gets modified.

The scripts do the counting. Your job is scoping, verification, and the written scope, method, summary and observations, which no script can produce. The transcript format has traps that silently inflate or deflate numbers by 10×. Read `references/transcript-format.md` before trusting any figure that looks surprising.

## Files

* `scripts/inventory.py`: lists the transcript folders and sessions for a path (branches, dates, titles, prompt counts). Use it to decide the scope.
* `scripts/sessions.py`: the token, cost, tool and time analysis. Writes `sessions.md`, `calls.csv` (one row per API call), `tools.csv` (one row per tool call) and `summary.json`.
* `scripts/gitstats.py`: commits (live, archived, backup, killed), refs, deleted branches, worktrees and LOC (net, gross, distinct), plus LOC by area. Writes `git[-name].md`, `git[-name]-appendix.md` and `git[-name]-summary.json`.
* `scripts/assemble.py`: joins your header with the generated sections into the final report and copies the CSVs.
* `references/transcript-format.md`: transcript locations, entry types, usage fields and the pitfalls list.
* `references/methodology.md`: the definition of every metric, the attribution rules, git classification, LOC views and pricing.
* `references/verification.md`: the checklist to run before handing over the report.
* `references/report-template.md`: header and executive-summary layout, observations worth looking for, and extensions.

All scripts use only the Python 3 standard library and `git`. Keep intermediate output in the session scratchpad (or the project's `./tmp` if the user prefers that). Write only the final report and CSVs into the project.

## Workflow

### 1. Pin down the scope

Ask only what the conversation and the inventory can't answer. The usual questions:
* **Which folders:** this checkout only, or its worktrees and sibling clones too.
* **Which branches:** a family like `feature-x*`, plus the branch the work started on.
* **Which dates:** "since last Monday" has to be resolved to a real date.
* **Whose commits:** usually only the user's. Team history is excluded through the main refs.
* **Where the report goes:** the default is `<project-root>/tokens-report.md`.

Run the inventory and look at it:

```bash
python3 <skill>/scripts/inventory.py --path <project-dir> --siblings
```

Separate in-scope folders from look-alikes, such as scratch clones or other projects that share a name prefix. Anything you exclude must still appear in the report with a reason; a user who sees a number shrink without explanation stops trusting the report.

### 2. Refresh prices

The defaults in `sessions.py` (`PRICE`) were correct when written. Prices change, so confirm current per-MTok prices for every model in scope (the `claude-api` skill has a cached table) and pass `--prices prices.json` for any that differ or are missing. The script warns on stderr about models it can't price.

### 3. Run the session analysis

```bash
python3 <skill>/scripts/sessions.py \
  --projects '~/.claude/projects/<encoded-prefix>*' \
  --exclude <folder-substring-to-skip> \
  --branch-regex '^(feature-x.*|main)$' \
  --since 2026-10-12 --tz 3 \
  --out <scratch>/token-analysis
```

* `--projects` takes several dirs or globs.
* `--sessions <id-prefix>…` pins explicit sessions.
* `--handoff-regex` marks agent-written briefs pasted as prompts, so they aren't counted as human typing.

Read `summary.json`, then check that the session count, date range and prompt count match the inventory.

### 4. Run the git analysis once per repository

```bash
python3 <skill>/scripts/gitstats.py --repo <repo> \
  --main main origin/main \
  --branch-regex 'feature-x' \
  --landed feature-x feature-x-integration \
  --since 2026-10-12 --tz 3 \
  --out <scratch>/token-analysis [--name <repo>]
```

* `--main` names the refs that hold pre-existing or team history. Everything reachable from them is excluded.
* `--landed` lists the refs that count as delivered, in priority order. Find the real integration line with `git merge-base --is-ancestor`: a squash or finish-branch flow may land work on a branch other than the obvious one, and the last `--landed` ref drives the net-LOC-by-area table.
* `--archive-regex` and `--backup-regex` classify archive refs (e.g. `completed/*`) and backups.
* `--areas` takes a JSON override for grouping LOC by project area.

Separate clones are separate repos; worktrees share one repository.

### 5. Verify

Go through `references/verification.md`. At minimum:
* Hand-check one session's token sum and the net LOC of the landed ref.
* Compare the transcript cost with the `cost-state` ledger.
* Confirm that only the user's commits are counted.
* Confirm the timezone.

Fix the scope and re-run rather than patching numbers in the report.

### 6. Write the header and assemble

Write the header following `references/report-template.md`: title, scope and method, executive summary, key observations. Every number in the summary must come from a generated table. Recompute shares and percentages from those tables rather than estimating them. Label each estimate as one, with its method: subagent output re-estimation, typing and reading time, per-prompt attribution. The gap between "recorded", "re-estimated" and "ledger" figures is a finding in itself, so explain it instead of picking one silently.

```bash
python3 <skill>/scripts/assemble.py --header <scratch>/header.md --work <scratch>/token-analysis \
  --report <project>/tokens-report.md --csv-dir <project>/tmp
```

### 7. Hand over

In the reply, give the headline numbers, the main caveats (subagent output undercount, inferred human time, attribution rule, exclusions) and the paths of the report and CSVs. Don't commit the report unless asked.

## Adapting to a new project

* **Bash purposes:** the regex list `CATS` in `sessions.py` recognizes common git, test, e2e, build, docker, process and agterm commands. If "other shell" is large in section 3.1, look at `tools.csv`, add patterns for the project's toolchain (`pytest`, `cargo`, `make`, `gradle`…) and re-run. Order matters, because the first match wins.
* **Code areas:** pass `--areas` with `[regex, label]` pairs so the LOC tables separate product code, tests, e2e and docs the way this project is organized.
* **Non-git or several repos:** skip or repeat step 4. The token and time analysis works without git.

## Ideas when the user wants more

See `references/report-template.md` § Extensions: cost per landed commit or LOC, waste on killed work, model-mix what-ifs, cache efficiency over time, dashboards from the CSVs.

# Report template and ideas

## Header (write it by hand, then pass it to `assemble.py --header`)

Generated sections start at `## 1.` (tokens), then `## 2.` sessions, `## 3.` tools, `## 4.` time, `## 5.` top requests and `## 6.` git. The header should contain:

```markdown
# Tokens, time and code report: <scope name>

Generated <date> from <transcript folders> and <repos>. Times in <tz>.

## 0. Scope and method
**In scope:** <whose work, which branches, which folders, which dates; N sessions>
<table: transcript folder → what it was (root checkout, worktree X since removed, ...)>
**Out of scope:** <each exclusion with a reason and, if cheap, its size>
**How the numbers were made:** <dedup, subagent output caveat, pricing basis and date, ledger cross-check,
per-prompt attribution rule, time definitions, git sources, where the raw CSVs are>

## Executive summary
<two-column table: period, sessions/subagents, human prompts, API calls, tokens (with the split),
cost (recorded / re-estimated / ledger), where the money went (by token class and model/thread),
tool calls, agent busy, human engaged (+ typing and reading estimates), e2e and test runs,
commits (created / landed / archived / killed), net LOC, gross churn, what the lines are>

Key observations: <3–7 numbered findings, each backed by a table below>
```

## Observations worth looking for

* Cost driven by context (cache reads) rather than output. Which threads grew huge, and how often auto-compaction fired.
* One branch or one prompt taking a disproportionate share. Name the prompt.
* Short prompts (`status`, `continue`, `go`) carrying big bills, because they resumed autonomous runs.
* Days with many agent-hours and few prompts (unattended runs), and the reverse (heavy hand-holding).
* Test execution and waiting (sleep/poll) dominating agent wall time.
* Subagent swarms: number spawned, cost per subagent type, Sonnet vs Opus split.
* Rewrite intensity: share of commits killed or archived, rebases in the reflog, gross churn vs net.
* What the code actually is: test, docs and plans vs product source.
* Agents pushing nothing (user pushes by hand) or committing more than once per change.
* Human latency: median gap between the end of a turn and the next prompt.

## Extensions (when the user asks for more)

* **Per-API-call or per-tool-call detail:** point to `calls.csv` and `tools.csv`, or load them into a spreadsheet or an HTML dashboard. Use the dataviz skill if you build charts.
* **Cost per commit or per landed LOC:** total cost / landed commits, or / net lines.
* **Cache efficiency over time:** cache-read share per day, compaction count per session.
* **Model mix advice:** price Sonnet subagents as Opus (or the reverse) to show the delta.
* **Waste:** spend on killed commits. Join commit time windows to calls by session and branch.
* **Several repos or several users:** run `gitstats.py --name <repo>` once per repo (writes `git-<repo>.md`; `assemble.py` picks up every `git*.md`), and run `sessions.py` with a different `--projects` per user's home.
* **Live or ongoing sessions:** the current session has no final `cost-state`. Mention that its numbers are partial.

# Methodology: what each number means and how it is computed

## Contents
1. Scoping
2. Tokens and cost
3. Attribution (per session, branch, prompt, subagent, day)
4. Tools
5. Time
6. Git: commits, killed work, LOC
7. Pricing table and how to refresh it

## 1. Scoping

The question is always "whose work, where, when". Settle it before computing anything, and print it in the report.

* **Where:** the transcript folders. Start with `scripts/inventory.py --path <project> --siblings` to see every folder that shares the project's encoded prefix, including worktrees and clones next to it. Scratch clones, other projects with a similar name and unrelated checkouts belong in `--exclude`.
* **Which work:** `--branch-regex` keeps a session if any entry records a matching branch. Include the branch the work started from if early sessions ran there, for example the docs session on `main` that seeded a research branch. Detached `HEAD` sessions in worktrees also count. `--sessions` pins explicit ids.
* **When:** `--since` / `--until`. If the user says "since last Monday", resolve it to a date and check it against the first event. Report the real first event if it differs, for example "you said Monday; the first session was Wednesday".
* **Whose commits:** the author regex and the `--main` refs. Everything reachable from `--main` is pre-existing or team history and is excluded. If the user only wants their own work, pick the `--main` refs so the team's feature branches are excluded too, and make sure the author regex matches only the user.

Anything excluded must still be named in the report with a one-line reason and, where cheap, its size. "Scratch repo `x`, 2 sessions, $9.82" is enough.

## 2. Tokens and cost

Per unique API response: `input` (uncached), `cache_write` (5 m + 1 h), `cache_read`, `output` (includes thinking). The per-response total is all four added together.

* **All tokens processed** is the sum of the totals. It is dominated by cache reads, because every call re-reads its context. State this, or the number looks absurd.
* **Cache hit ratio** = read / (read + write + uncached input).
* **Input:output ratio** shows the cost is context, not writing.
* **Output re-estimate** is the max of the recorded output and content chars / 3.5. It corrects the subagent placeholder (see transcript-format.md, pitfall 2).
* **Cost** is the sum over token classes of tokens × price per MTok. If a response reports no 5 m/1 h split, price the whole cache write at the 5 m rate. Show the split by class (cache read, cache write, output, input), because cache reads usually make up half or more.
* **Cross-check:** the sum of max `cost-state.totalCostUSD` per session. Expect it to be 5–15% above the transcript cost. Explain larger gaps.
* **Unknown models** get no price. The script warns, and you add them via `--prices` instead of silently counting $0.

This is the pay-as-you-go API price. Users on a subscription are not billed this, so say so.

## 3. Attribution

* **Session:** main thread plus all of its subagents.
* **Branch:** the `gitBranch` on each call. Subagent calls without one fall under "(none recorded)".
* **Prompt:** each call, main or subagent, is charged to the latest human prompt in the same session at or before it. Background agents and autonomous loops get charged to whatever the user last typed. A one-word `status` can therefore carry a $50 bill. Point this out when it happens, because it means the prompt resumed a long run.
* **Subagent:** the meta.json `agentType`, `description` and `model`, plus lifetime (first to last event).

## 4. Tools

From `tool_use` blocks, deduplicated by id, matched to `tool_result` by `tool_use_id`.

* Count, number in subagents, errors (`is_error`), wall time (result ts − use ts), median, result chars. Result chars / 4 approximates the tokens the result adds to every later call in that thread until compaction. That is the hidden cost of verbose tools.
* **Bash by purpose:** a regex classifier in `sessions.py` (`CATS`). The first match wins, so order matters: commit and push come before generic git reads, and e2e before unit tests. Adjust `CATS` to the project's toolchain (`pytest`, `cargo test`, `go test`, `npm test`, `make`…) when the "other shell" bucket is large. Inspect it in `tools.csv`.
* Background commands are counted but their runtime is unknown. Long sleep/poll categories usually mean agents waiting on background jobs.
* Files edited or written: the `file_path` of Edit/Write calls.

## 5. Time

Report each metric with its definition. They answer different questions.

| Metric | Definition | Answers |
|---|---|---|
| Calendar span | First to last event | "How long has this been going on" |
| Activity blocks | Union of all event timestamps, merged when < 10 min apart | Wall clock with anything happening |
| Agent busy (union) | Union of `[ts − durationMs, ts]` over all `turn_duration` | Wall clock with at least one agent working |
| Agent-hours (sum) | Sum of `durationMs` | Total agent effort when sessions run in parallel |
| Subagent lifetimes | First to last event per subagent, summed, plus the union with main turns | |
| Human engaged | Prompts < 30 min apart merged into blocks | A lower bound on attended time |
| Think/read/type gaps | End of the previous agent turn to the next prompt in that session; median, sum capped at 15 min | Human response latency |
| Typing estimate | Typed chars / 200 chars/min (≈ 40 wpm), slash commands excluded | |
| Reading estimate | Main-thread visible text / 1,250 chars/min (≈ 250 wpm) | An upper bound; nobody reads all of it |

Also give a per-day table and an hour-of-day heatmap of prompts. Show agent work per category: Playwright and e2e, unit tests, typecheck, lint and build, git commit and push, restarts and port kills, docker, and sleep/poll. These come from Bash wall time per purpose.

## 6. Git

Run `scripts/gitstats.py` once per repository. Worktrees share one repository; separate clones don't.

**Collection:** commits matching the author that are not reachable from `--main`, taken from three places:
1. every scanned ref (local branches and remotes),
2. the reflog: rewritten work whose branch still had a reflog,
3. `git fsck --unreachable --no-reflogs`: dangling commits not yet garbage-collected. These have no branch, so bound them with `--since`.

**Status per commit**, first match wins:
1. landed on each `--landed` ref, in the given order,
2. archived (`--archive-regex`, e.g. `completed/*`),
3. on another branch,
4. backup ref only,
5. killed, reflog only,
6. killed, dangling.

`git gc` may already have pruned old dangling commits. Say "at least N killed".

**Dedup:** `git patch-id --stable` collapses rebased and cherry-picked copies into distinct changes.

**LOC, three views. Always say which one a number is.**
* *Net*: `git diff --shortstat <merge-base(landed, main)> <landed>`. This is what actually changed in the codebase.
* *Gross churn, all commits*: the sum of numstat over every non-merge commit, killed and copies included. This is how much the agents wrote and rewrote.
* *Gross churn, distinct patches*: the same, but deduplicated by patch-id.
* *Claude Code's ledger*: the `cost-state` `totalLinesAdded` / `totalLinesRemoved`, counting lines written through Edit/Write only. Code generated by Bash, scripts or `git` is invisible to it.

**By area:** a generic classifier covering lockfiles, tests, docs, top-level dirs and `apps/x`/`packages/x` in monorepos. Override it with `--areas areas.json` (`[["^apps/e2e/", "e2e suite"], …]`, in order). Separate test code, docs and product source. The ratio between them is often the most telling finding.

Also report: commits per day, refs with first and last dates, deleted branches recovered from reflog names, live worktrees, conventional-commit types, Claude co-author trailers and reflog actions (rebases and resets show rewrite intensity).

Agent `git push` count comes from the Bash tool calls. If remote branches exist but agents pushed little, the user pushed by hand. Say so.

## 7. Pricing

Defaults live in `sessions.py` (`PRICE`) as $/MTok: input, output, cache read, cache write 5 m, cache write 1 h. Cache write is 1.25× input for 5 m and 2× input for 1 h; cache read is model-specific, usually 0.1×. **Refresh prices before each report.** Use the `claude-api` skill or the live pricing page, then pass `--prices prices.json` for any model whose price changed or is missing:

```json
{"claude-opus-5-5": [4.0, 20.0, 0.20, 5.0, 8.0]}
```

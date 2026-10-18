# Claude Code transcript format (what the scripts rely on)

Observed on Claude Code 2.1.3xx. Formats drift between versions. If a number looks wrong, open a transcript and check these fields again before trusting the scripts.

## Where transcripts live

* `~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl` holds one main thread per file. `<encoded-cwd>` is the absolute working directory with every non-alphanumeric character replaced by `-`. For example, `/Users/me/src/app` becomes `-Users-me-src-app`.
* Every worktree, clone or sibling folder gets its own encoded folder: `-Users-me-src-app-worktree-x`, `-Users-me-src-app--claude-worktrees-x` (Claude-managed worktrees under `.claude/worktrees/`). The folders survive after the worktree is deleted, so they are the only record of removed worktrees.
* `<sessionId>/subagents/agent-<id>.jsonl` holds one subagent transcript. The sibling `agent-<id>.meta.json` holds `agentType`, `description`, `model`, `toolUseId` (the `Agent` tool call in the parent) and `spawnDepth`.
* `<sessionId>/tool-results/` holds tool outputs that were too large to inline.
* `memory/` holds auto-memory. It is not a transcript.

## Entry types that matter

Each line is a JSON object with a `type`.

| type | Use |
|---|---|
| `assistant` | One content block of a model response. `message.id` and `requestId` identify the API call. `message.model` and `message.usage` carry tokens. `gitBranch`, `cwd`, `timestamp` and `isSidechain` are also set. |
| `user` | A human prompt, a tool result (`message.content[].type == "tool_result"` with `tool_use_id`), a task notification or a meta line. `toolUseResult` holds structured tool output (stdout/stderr, structuredPatch for edits). |
| `system` with `subtype: "turn_duration"` | `durationMs` is how long the main thread worked on one prompt. `messageCount` and `pendingBackgroundAgentCount` are also set. |
| `system` with `subtype: "compact_boundary"` | A context compaction. `compactMetadata.trigger` is auto or manual, plus `preTokens` and `durationMs`. |
| `system` with `subtype: "stop_hook_summary"` and `local_command` | Hook timings, slash commands. |
| `cost-state` | Claude Code's own cumulative ledger per session: `totalCostUSD`, `modelUsage{model: {inputTokens, outputTokens, thinkingTokens, cacheReadInputTokens, cacheCreationInputTokens, costUSD}}`, `totalDuration`, `totalAPIDuration`, `totalToolDuration`, `totalLinesAdded`, `totalLinesRemoved`. Written a few times per session; take the max per session. Missing when a session never wrote one, for example while it is still running. |
| `api-request` | The request side. `querySource` is `repl_main_thread`, `agent:builtin:general-purpose`, `agent:builtin:Explore`, `agent:builtin:fork` and so on; `params.model` is set. Not present in every version. Usage is not logged here. |
| `ai-title`, `custom-title`, `agent-name` | Session naming. |
| `worktree-state`, `relocated` | The session moved into a worktree (`EnterWorktree`). |
| `queue-operation` | A prompt queued while the agent was busy. It reappears later as a `user` entry, so do not count both. |
| `file-history-snapshot` / `-delta` | Edit checkpoints. |

## Usage fields (`message.usage`)

`input_tokens` (uncached), `cache_creation_input_tokens`, `cache_creation.ephemeral_5m_input_tokens`, `cache_creation.ephemeral_1h_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `output_tokens_details.thinking_tokens` (newer versions only), `iterations[]`, `speed`, `service_tier`.

## Pitfalls (each one produced a wrong number at least once)

1. **One API response becomes several `assistant` lines**, one per content block, each repeating the usage. Deduplicate by `message.id`, falling back to `requestId`. Take the max of each usage field across the lines.
2. **Subagent `output_tokens` is a stream-start placeholder.** It is often 1–20 tokens even for long tool calls, so subagent output is undercounted by an order of magnitude. Re-estimate from visible content: text plus the `json.dumps` of tool_use inputs, at about 3.5 chars per token. Hidden thinking can't be recovered, so the estimate is still a floor. Main-thread usage looks final. `cost-state` holds the real totals.
3. **Resumed or forked sessions copy history** into a new file. Global dedup by `message.id` keeps it from being counted twice.
4. **`model == "<synthetic>"`** marks a locally generated message (errors, interrupts). Skip it.
5. **Human prompts:** `type == "user"`, not `isMeta`, not `isSidechain`, and `origin.kind == "human"`. Other user entries are tool results, `<task-notification>` (background agent finished), compact summaries (`isCompactSummary`), `<local-command-stdout>` and `<bash-stdout>`.
   * Slash commands show up as `<command-message>` / `<command-name>` with `origin.kind == human`. They count as prompts but involve almost no typing.
   * Hand-off briefs that another agent pasted into a new session still have `origin.kind == human`. Detect them by content, for example a fixed `# Brief` heading, and report them separately.
   * The same prompt can be logged twice within seconds (retry or resume). Collapse identical text in one session within about 2 minutes.
6. **`gitBranch` is recorded per entry**, so one session can span several branches. Filter sessions by "any entry matches". Attribute calls by the branch on each call. Subagent entries often carry no branch.
7. **Timestamps are UTC ISO strings.** Convert to the user's timezone before bucketing by day or hour.
8. **`turn_duration` covers the main thread only.** It includes time blocked on long foreground tools and on waiting for background agents. Turns of parallel sessions overlap, so take the union for wall clock and the sum for total agent-hours.
9. **Tool timing** is the gap between the `tool_use` timestamp and the matching `tool_result` timestamp. Background Bash (`run_in_background: true`) returns at once, so its real runtime is invisible here. The completion arrives later as a task notification.
10. **`cost-state` and transcript totals differ.** The ledger also counts side calls the transcripts don't log (titles, permission classifier, compaction summaries) and real subagent output. Report both and explain the gap.

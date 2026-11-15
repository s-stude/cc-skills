# Claude Code transcript format (.jsonl)

What the parser relies on, and the traps found while auditing real transcripts (Claude Code 2.1.x, 2026-10/11).
Re-check field names on a new Claude Code version: `python3 -I scripts/cc_jsonl.py extract` prints entry types,
and a quick key census tells you if something moved (snippet at the bottom).

## Where transcripts live

- `~/.claude/projects/<slug>/` holds one folder per project.
  - The slug is the session's cwd with every non-alphanumeric character turned into `-`. For example,
    `/Users/me/src/app` becomes `-Users-me-src-app`.
  - A worktree has its own slug.
- `<session-id>.jsonl`: a main session.
- `<session-id>/subagents/agent-<id>.jsonl`: one subagent's transcript.
- `agent-<id>.meta.json` beside it holds:
  - `description`: the title the coordinator gave it;
  - `agentType`;
  - `requestShape` (`background` …);
  - `finished`;
  - `spawnDepth`.
- The coordinator of a subagent is the main session with the same `<session-id>`. Its transcript holds the `Agent` /
  `SendMessage` calls that briefed the subagent and what it did with the reports.

## Lines

One JSON object per line; `type` says what it is.

| `type` | What it is | Notes |
|---|---|---|
| `user` | a prompt, a tool result, a harness message | `message.content` is a string or a list of blocks |
| `assistant` | model output | holds `usage`, `stop_reason`, `model`, `id` |
| `attachment` | files and images the harness attached | |
| `api-request`, `api-request-shape`, `api-request-blob` | logged API requests | a blob's `message` is a string repr of a full message, images included; some `api-request` lines carry a `message` **dict** with `tool_use` blocks, so filter on `type` before counting tool calls |
| `system` | `subtype` `turn_duration`, `stop_hook_summary`, … | main sessions |
| `last-prompt`, `mode`, `permission-mode`, `ai-title`, `queue-operation`, `bridge-session`, `file-history-*`, `cost-state`, `tools-used` | session bookkeeping | main sessions; tiny |

Common fields: `timestamp` (ISO UTC; missing on some bookkeeping lines), `sessionId`, `agentId`, `uuid`,
`parentUuid`, `isSidechain` (true inside a subagent), `cwd`, `gitBranch`, `version`.

## Blocks inside `message.content`

- **`text`:** `{type, text}`.
- **`tool_use`:** `{type, id, name, input}`. Tool names:
  - `Read`, `Bash`, `Grep`, `Glob`, `Edit`, `Write`;
  - `Agent`, `SendMessage`, `SubagentHandback`, `Workflow`;
  - MCP tools, named `mcp__<server>__<tool>`.
- **`tool_result`:** `{type, tool_use_id, content}`. `content` is a string or a list of `text` and `image` blocks.
- **`image`:** `{type, source: {type: base64, media_type, data}}`. The PNG width and height are bytes 16–24 of
  the decoded data.

## Counting rules

- **One API response spans several `assistant` lines that share `message.id`.** Count `usage`, `model` and
  `stop_reason` once per id, or every number doubles.
- **Context at a call** = `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
- **A full cache rewrite:** `cache_creation_input_tokens` near the whole context. It happens after an idle gap
  longer than the cache lifetime (5 minutes by default), and after stream errors.
- **The subagent's report** is the `input.message` of its last `SubagentHandback` tool_use. Without one, take the
  last assistant `text`.
- **Every image is stored three times:** in `message.content`, in the line's `toolUseResult`, and in an
  `api-request-blob`. That, not the text, is why transcripts reach 50–160 MB.

## User lines that are not a new instruction

- `tool_result`-only content.
- `image`-only content (attachments).
- Text starting with `<system-reminder>`, `<command-` or `<local-command`.
- Harness nudges: "Your response above was cut off mid-stream…", and `[handback-send-enforce]` when a subagent
  wrote its report as text instead of calling SubagentHandback.
- **Two cases that do start a round:**
  - **A coordinator message to a running or finished subagent** arrives as a `user` line with `isMeta: true`,
    `origin: {kind: "coordinator"}` and text "The coordinator sent a message while you were working:…". The
    wording appears even when the agent had already finished.
  - **In main sessions, `<task-notification>` user lines** (a background task or subagent finished) are harness
    events that start a round. `extract` labels each round's trigger: `first`, `user`, `coordinator` or
    `notification`.

## Anomalies

- **`stop_reason` `stop_sequence` with 0 output tokens and `model: "<synthetic>"`:** a harness-made message. Its
  text says what happened, for example "API Error: Connection lost mid-response", "EPROTO", or "You've hit your
  weekly limit".
- **`end_turn` with under ~50 output tokens,** often followed by a cut-off nudge: the model stopped early.
- **`max_tokens`:** the output was truncated.

## Key census, for a new Claude Code version

```python
import collections, json, sys
types, keys, subtypes = collections.Counter(), collections.Counter(), collections.Counter()
for line in open(sys.argv[1]):
	d = json.loads(line); types[d.get("type")] += 1; keys.update(d.keys())
	if d.get("type") == "system": subtypes[d.get("subtype")] += 1
print(types, subtypes, [k for k, _ in keys.most_common(50)], sep="\n")
```

# Skills

Claude Code agent skills I've built across different projects.

## Install

Each skill has its own `install.sh` that symlinks it into `~/.claude/skills/<name>`:

```sh
./doc-review/install.sh
```

It can be run from any directory and is safe to re-run. It won't overwrite a real directory at the target path.

## Workflow

| Skill | What it does |
|---|---|
| [start-branch](start-branch) | Starts work in a new branch and sibling worktree, writes a brief, opens a Claude session there |
| [finish-branch](finish-branch) | Checks plans were implemented, backlogs leftovers, squash-merges and archives the branch |
| [backlog](backlog) | Files, dedupes and closes deferred work items in `docs/backlog/` |
| [learn-from-session](learn-from-session) | Saves what a session learned into `CLAUDE.md` |
| [doc-review](doc-review) | Reviews docs like code: gaps, conflicts, broken links, stale references |
| [token-analysis](token-analysis) | Reports tokens, cost, tool calls and time spent across past Claude Code sessions |
| [peer-chat](peer-chat) | Lets Claude Code and Codex talk as peers in an agterm split (installs for both, plus a helper script) |
| [autopilot-developer](autopilot-developer) | Plans and implements a request unattended, one commit per task, with the other agent reviewing over peer-chat (installs for both; needs peer-chat) |

## Development

| Skill | What it does |
|---|---|
| [nodejs-architecture](nodejs-architecture) | Guide to modular, plug-and-play Node.js backends |
| [serve-static](serve-static) | Serves static files locally with `npx serve` and an `npm start` script |

## Project-specific

| Skill | What it does |
|---|---|
| [petroleum-jobs](petroleum-jobs) | Rigzone pipeline: collect job URLs, save each post as markdown, normalize it to JSON |
| [airport-jobs](airport-jobs/skills) | Turn a job URL or text into JSON, then assign it a category |

These hold several skills each; every sub-skill has its own `install.sh`.

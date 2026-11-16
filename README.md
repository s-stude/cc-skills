# Skills

Claude Code agent skills I've built or collected across different projects.

## Install

Link every skill at once, or one skill by its folder. The `-cc` scripts link into `~/.claude/skills` for Claude Code, the `-codex` ones into `${CODEX_HOME:-~/.codex}/skills`; `unlink-*` removes those links again:

```sh
./link-all-cc.sh                                # every skill
./unlink-all-cc.sh
./link-one-cc.sh _workflow/start-branch/        # one skill: ~/.claude/skills/start-branch
./unlink-one-cc.sh _workflow/start-branch/
./link-all-codex.sh                             # the same for Codex
```

`*-all-*` finds every folder with a `SKILL.md` at any depth and runs the matching `*-one-*` on it. It skips `plugins/`, which are installed as plugins, and any skill whose `name:` differs from its folder name or repeats another skill's folder name, since those would clash.

They run from any directory and are safe to re-run. They only touch their own links: a real directory, or a symlink to somewhere else, is reported and left alone.

[peer-chat](peer-chat) is the one skill with its own `install.sh`, needed for the full setup: besides the skill links it puts two commands on `PATH` and adds Codex rules. It relinks those two commands in `~/.local/bin` (moving a real file there aside as a backup); its skill links follow the same rule as the root scripts.

## Workflow

| Skill | What it does |
|---|---|
| [start-branch](_workflow/start-branch) | Starts work in a new branch and sibling worktree, writes a brief, opens a Claude session there |
| [finish-branch](_workflow/finish-branch) | Checks plans were implemented, backlogs leftovers, squash-merges and archives the branch |
| [autopilot-developer](_workflow/autopilot-developer) | Plans and implements a request unattended, one commit per task, with the other agent reviewing over peer-chat (needs peer-chat) |
| [backlog](_workflow/backlog) | Files, dedupes and closes deferred work items in `docs/backlog/` |
| [commit-code](_workflow/commit-code) | Commits the changes for a feature with a clear message |
| [doc-review](_workflow/doc-review) | Reviews docs like code: gaps, conflicts, broken links, stale references |

## Coding

| Skill | What it does |
|---|---|
| [nodejs-architecture](_coding/nodejs-architecture) | Guide to modular, plug-and-play Node.js backends |
| [software-engineering-logging-guidelines](_coding/software-engineering-logging-guidelines) | When and how to add logging to code |

## Tools

| Skill | What it does |
|---|---|
| [peer-chat](peer-chat) | Lets Claude Code and Codex talk as peers in an agterm split through message files (installs for both, plus two commands on `PATH`) |
| [token-analysis](token-analysis) | Reports tokens, cost, tool calls and time spent across past Claude Code sessions |
| [learn-from-session](learn-from-session) | Saves what a session learned into `CLAUDE.md` |
| [find-docs](find-docs) | Looks up library and framework documentation |
| [serve-static](serve-static) | Serves static files locally with `npx serve` and an `npm start` script |
| [telegram-mcp-setup](telegram-mcp-setup) | Wizard for connecting Telegram to Claude Code via telegram-mcp |

## Project-specific

| Skill | What it does |
|---|---|
| [petroleum-jobs](_project-related/petroleum-jobs) | Rigzone pipeline: collect job URLs, save each post as markdown, normalize it to JSON |
| [airport-jobs](_project-related/airport-jobs/skills) | Turn a job URL or text into JSON, then assign it a category |

These hold several skills each.

## Credits

[peer-chat](peer-chat) started from someone else's recipe and has since been rewritten; [telegram-mcp-setup](telegram-mcp-setup) is a copy of someone else's work. Their READMEs link the originals.

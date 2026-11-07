# Skills

Claude Code agent skills I've built or collected across different projects.

## Install

Each skill has its own `install.sh` that symlinks it into `~/.claude/skills/<name>`. Skills that also work in Codex have `install-claude.sh` and `install-codex.sh` instead; the Codex one links into `~/.codex/skills/<name>` (or `$CODEX_HOME/skills`):

```sh
./_workflow/doc-review/install-claude.sh
./_workflow/doc-review/install-codex.sh
```

It can be run from any directory and is safe to re-run. It won't overwrite a real directory at the target path.

To link every skill into one project's `.claude/skills` instead:

```sh
./link-skills.sh ~/path/to/project
```

## Workflow

| Skill | What it does |
|---|---|
| [start-branch](_workflow/start-branch) | Starts work in a new branch and sibling worktree, writes a brief, opens a Claude session there |
| [finish-branch](_workflow/finish-branch) | Checks plans were implemented, backlogs leftovers, squash-merges and archives the branch |
| [autopilot-developer](_workflow/autopilot-developer) | Plans and implements a request unattended, one commit per task, with the other agent reviewing over peer-chat (installs for Claude and Codex; needs peer-chat) |
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
| [peer-chat](peer-chat) | Lets Claude Code and Codex talk as peers in an agterm split (installs for both, plus a helper script) |
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

These hold several skills each; every sub-skill has its own `install.sh`.

## Credits

[peer-chat](peer-chat) and [telegram-mcp-setup](telegram-mcp-setup) are copies of other people's work; their READMEs link the originals.

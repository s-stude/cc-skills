# peer-chat

Lets Claude Code and Codex, running in the two panes of an agterm split, talk to each other as peers.

## Source

This skill is a copy of the agterm cookbook recipe
[`cookbook/two-agent-chat/SKILL-claude.md`](https://github.com/umputun/agterm/blob/f6cf8bff263b5c7e0b840ee1958a6112e1944c8d/cookbook/two-agent-chat/SKILL-claude.md)
by [umputun](https://github.com/umputun).

## Layout

- `claude/SKILL.md` - the Claude Code side
- `codex/SKILL.md` - the Codex side
- `bin/peer-chat.py` - sends a message into the other pane; both skills call it through `PATH`

## Install

```sh
./install.sh
```

Symlinks `claude/` to `~/.claude/skills/peer-chat`, `codex/` to `~/.codex/skills/peer-chat`, and
`bin/peer-chat.py` to `~/.local/bin/peer-chat.py`. `~/.local/bin` must be on `PATH`.

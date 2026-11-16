# peer-chat

Lets Claude Code and Codex, running in the two panes of an agterm split, talk to each other as peers through
message files in `.peer-chats/chat-NNN/`.

## Source

Started from the agterm cookbook recipe
[`cookbook/two-agent-chat/SKILL-claude.md`](https://github.com/umputun/agterm/blob/f6cf8bff263b5c7e0b840ee1958a6112e1944c8d/cookbook/two-agent-chat/SKILL-claude.md)
by [umputun](https://github.com/umputun), since rewritten.

## Layout

- `SKILL.md` - the skill, shared by Claude Code and Codex
- `scripts/peer-chat.py` - message files: `new`, `send`, `read`, `path`; on `PATH` as `peer-chat-files.py`
- `scripts/peer-chat-typing.py` - types the one-line pointer into the other pane; on `PATH` as `peer-chat.py`
- `scripts/test_*.py` - tests: `python3 -m unittest discover -s scripts -p "test_*.py"`
- `install.sh`, `uninstall.sh` - full setup and its undo

## Install

```sh
./install.sh
```

Links this folder into `~/.claude/skills/peer-chat` and `~/.codex/skills/peer-chat`, the two scripts into
`~/.local/bin`, and adds the Codex allow rules to `~/.codex/rules/default.rules`. `~/.local/bin` must be on
`PATH`. See *Setup* in `SKILL.md` for the details.

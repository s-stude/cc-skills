#!/bin/sh
set -e

src="$(cd "$(dirname "$0")" && pwd -P)"

link() {
  target="$1"
  dest="$2"
  mkdir -p "$(dirname "$dest")"

  if [ -L "$dest" ]; then
    if [ "$(readlink "$dest")" = "$target" ]; then
      echo "already installed: $dest -> $target"
      return 0
    fi
    echo "Replacing existing symlink $dest -> $(readlink "$dest")"
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "Error: $dest exists and is not a symlink; remove it manually first" >&2
    return 1
  fi

  ln -s "$target" "$dest"
  echo "Installed: $dest -> $target"
}

status=0
link "$src/claude" "$HOME/.claude/skills/peer-chat" || status=1
link "$src/codex" "$HOME/.codex/skills/peer-chat" || status=1
link "$src/bin/peer-chat.py" "$HOME/.local/bin/peer-chat.py" || status=1

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo "Note: $HOME/.local/bin is not on PATH; the skills call peer-chat.py through PATH" >&2 ;;
esac

exit $status

#!/bin/sh
set -e

src="$(cd "$(dirname "$0")" && pwd -P)"
name="$(basename "$src")"

link() {
  dest="$1/$name"
  mkdir -p "$1"

  if [ -L "$dest" ]; then
    if [ "$(readlink "$dest")" = "$src" ]; then
      echo "already installed: $dest -> $src"
      return 0
    fi
    echo "Replacing existing symlink $dest -> $(readlink "$dest")"
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "Error: $dest exists and is not a symlink; remove it manually first" >&2
    return 1
  fi

  ln -s "$src" "$dest"
  echo "Installed: $dest -> $src"
}

status=0
link "$HOME/.claude/skills" || status=1
link "$HOME/.codex/skills" || status=1

if ! command -v peer-chat.py >/dev/null 2>&1; then
  echo "Note: peer-chat.py not found on PATH; install peer-chat too (../peer-chat/install.sh)" >&2
fi

exit $status

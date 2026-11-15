#!/bin/sh
set -e

src="$(cd "$(dirname "$0")" && pwd -P)"
name="$(basename "$src")"
skills_dir="$HOME/.claude/skills"
dest="$skills_dir/$name"

mkdir -p "$skills_dir"

if [ -L "$dest" ]; then
  if [ "$(readlink "$dest")" = "$src" ]; then
    echo "$name already installed -> $src"
    exit 0
  fi
  echo "Replacing existing symlink $dest -> $(readlink "$dest")"
  rm "$dest"
elif [ -e "$dest" ]; then
  echo "Error: $dest exists and is not a symlink; remove it manually first" >&2
  exit 1
fi

ln -s "$src" "$dest"
echo "Installed $name: $dest -> $src"

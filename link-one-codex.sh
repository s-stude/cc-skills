#!/usr/bin/env bash
# link-one-<agent>.sh <skill-folder> links the folder (it must hold a SKILL.md) into the agent's skills folder as
# <folder name>; unlink-one-<agent>.sh removes that link. <agent> is cc (~/.claude/skills) or codex
# (${CODEX_HOME:-~/.codex}/skills). All four files have the same content and read their job from their own name.
# Run from anywhere; safe to rerun.
# Touches only its own link: a real directory, or a symlink to somewhere else, is reported and left alone.
# Exit codes: 0 done, 1 a link in the way, 2 bad usage, 3 skipped because the skill's `name:` differs from its
# folder name (the link would carry the wrong name).
set -euo pipefail

if [ $# -ne 1 ] || [ "${1#-}" != "$1" ]; then
  echo "usage: $0 <skill-folder>" >&2
  exit 2
fi
skill_arg="$1"
own="$(basename "${BASH_SOURCE[0]}")"
remove=""
case "$own" in unlink-*) remove=1 ;; esac

if [ ! -f "$skill_arg/SKILL.md" ]; then
  echo "error: $skill_arg has no SKILL.md" >&2
  exit 2
fi
skill_dir="$(cd "$skill_arg" && pwd -P)"
folder="$(basename "$skill_dir")"

case "$own" in
  *-codex.sh) target_dir="${CODEX_HOME:-$HOME/.codex}/skills" ;;
  *) target_dir="$HOME/.claude/skills" ;;
esac
link="$target_dir/$folder"

declared="$(sed -n '2,/^---$/s/^name:[[:space:]]*//p' "$skill_dir/SKILL.md" | head -1 | tr -d "\"'")"
if [ -n "$declared" ] && [ "$declared" != "$folder" ]; then
  echo "skip:    $skill_dir declares name '$declared', not its folder name '$folder'" >&2
  exit 3
fi

if [ -L "$link" ] && [ "$(readlink "$link")" = "$skill_dir" ]; then
  if [ -n "$remove" ]; then
    rm "$link"
    echo "removed: $link"
  else
    echo "ok:      $link -> $skill_dir"
  fi
  exit 0
fi
if [ -L "$link" ]; then
  echo "WARN: $link is a symlink to '$(readlink "$link")', not to $skill_dir; left untouched" >&2
  exit 1
fi
if [ -e "$link" ]; then
  echo "WARN: $link is a real directory or file, not a symlink; left untouched" >&2
  exit 1
fi
if [ -n "$remove" ]; then
  echo "absent:  $link"
  exit 0
fi

mkdir -p "$target_dir"
ln -s "$skill_dir" "$link"
echo "linked:  $link -> $skill_dir"

#!/usr/bin/env bash
set -euo pipefail

skills_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$skills_dir")"
target_dir="$project_root/.claude/skills"

mkdir -p "$target_dir"

for skill in "$skills_dir"/*/; do
  name="$(basename "$skill")"
  [ -f "$skill/SKILL.md" ] || continue

  link="$target_dir/$name"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "skip: $link exists and is not a symlink" >&2
    continue
  fi

  ln -sfn "../../skills/$name" "$link"
  echo "linked: .claude/skills/$name -> skills/$name"
done

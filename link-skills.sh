#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <project-dir>" >&2
  echo "Symlinks every skill in this repo into <project-dir>/.claude/skills" >&2
  exit 1
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
target_dir="$(cd "$1" && pwd -P)/.claude/skills"
mkdir -p "$target_dir"

# peer-chat keeps its Claude side in claude/ and its Codex side in codex/
while IFS= read -r skill_md; do
  skill="$(dirname "$skill_md")"
  case "$skill" in
    */codex) continue ;;
    */claude) name="$(basename "$(dirname "$skill")")" ;;
    *) name="$(basename "$skill")" ;;
  esac

  link="$target_dir/$name"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "skip: $link exists and is not a symlink" >&2
    continue
  fi

  ln -sfn "$skill" "$link"
  echo "linked: $link -> $skill"
done < <(find "$repo" -name SKILL.md -not -path '*/.git/*' -not -path '*/.claude/*' | sort)

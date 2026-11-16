#!/usr/bin/env bash
# link-all-<agent>.sh / unlink-all-<agent>.sh: finds every folder with a SKILL.md in this repository, at any depth,
# and runs the matching link-one-<agent>.sh / unlink-one-<agent>.sh on it. All four files have the same content and
# read their job from their own name. Run from anywhere; safe to rerun.
# Skipped, reported but not counted as failures: plugins/ (installed as plugins), a skill whose `name:` differs from
# its folder name, and a skill whose folder name another skill already uses. Exit 1 if any link was in the way.
set -euo pipefail

if [ $# -gt 0 ]; then
  echo "usage: $0" >&2
  exit 2
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
own="$(basename "${BASH_SOURCE[0]}")"
one="$repo/${own/-all-/-one-}"
problems=0
seen=" "

while IFS= read -r skill_md; do
  skill_dir="$(dirname "$skill_md")"
  folder="$(basename "$skill_dir")"
  case "$seen" in
    *" $folder "*)
      echo "skip:    ${skill_dir#"$repo"/} has the same folder name as another skill" >&2
      continue
      ;;
  esac
  status=0
  "$one" "$skill_dir" || status=$?
  case "$status" in
    3) continue ;;
    0) ;;
    *) problems=$((problems + 1)) ;;
  esac
  # only a skill the one-script accepted claims its folder name, so a skipped one can't block a later valid one
  seen="$seen$folder "
done < <(find "$repo" \( -name .git -o -name node_modules -o -name tmp -o -path "$repo/plugins" \) -prune \
  -o -name SKILL.md -type f -print | sort)

if [ "$problems" -gt 0 ]; then
  echo "$problems skill(s) not done, see the messages above" >&2
  exit 1
fi

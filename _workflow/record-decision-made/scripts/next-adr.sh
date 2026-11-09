#!/usr/bin/env bash
# Print the path of the next ADR file: docs/adr/NNN-<slug>.md, one above the highest existing number.
# Usage: next-adr.sh <slug> [adr-dir]
set -euo pipefail

slug="${1:-}"
dir="${2:-}"
if [[ -z "$slug" ]]; then
  echo "usage: next-adr.sh <slug> [adr-dir]" >&2
  exit 2
fi

if [[ -z "$dir" ]]; then
  root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  dir="$root/docs/adr"
fi

slug="$(printf '%s' "$slug" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
if [[ -z "$slug" ]]; then
  echo "slug is empty after cleaning" >&2
  exit 2
fi

max=0
if [[ -d "$dir" ]]; then
  for f in "$dir"/[0-9][0-9][0-9]-*.md; do
    [[ -e "$f" ]] || continue
    n="$(basename "$f" | cut -c1-3)"
    n=$((10#$n))
    (( n > max )) && max=$n
  done
fi

next=$(printf '%03d' $((max + 1)))
rel="${dir#"$(git rev-parse --show-toplevel 2>/dev/null || pwd)/"}"
echo "$rel/$next-$slug.md"

#!/usr/bin/env bash
# Reserves and prints the next .handoffs/brief-NNN.md under ROOT (default: the git top level, else the working
# directory). brief-NNN is what starts session NNN, whose peer transcript is .peer-chats/chat-NNN.md, so NNN is one
# past the highest brief or transcript number: the session writing the brief is the highest so far. The first session
# of a worktree, which had no brief, is 000. Creates .handoffs/ and, inside a git checkout, keeps .handoffs/ and
# .peer-chats/ out of git through the local exclude file (never .gitignore).
set -euo pipefail

root="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
dir="$root/.handoffs"
mkdir -p "$dir"

if git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
	exclude="$(git -C "$root" rev-parse --git-path info/exclude)"
	[[ "$exclude" = /* ]] || exclude="$root/$exclude"
	mkdir -p "$(dirname "$exclude")"
	for name in .handoffs .peer-chats; do
		git -C "$root" check-ignore -q "$name/x" || printf '%s\n' "$name/" >> "$exclude"
	done
fi

highest=0
for file in "$dir"/brief-[0-9]*.md "$root"/.peer-chats/chat-[0-9]*.md; do
	[ -e "$file" ] || continue
	digits="$(basename "$file" .md)"
	digits="${digits##*-}"
	[[ "$digits" =~ ^[0-9]+$ ]] || continue
	(( 10#$digits > highest )) && highest=$((10#$digits))
done
number=$((highest + 1))

# noclobber makes the reservation atomic, so two handoffs at once cannot get the same number
while :; do
	path="$dir/$(printf 'brief-%03d.md' "$number")"
	if (set -C; : > "$path") 2>/dev/null; then
		echo "$path"
		exit 0
	fi
	number=$((number + 1))
done

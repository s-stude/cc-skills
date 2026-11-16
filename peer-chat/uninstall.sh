#!/usr/bin/env bash
# Removes what install.sh added: the skill links in ~/.claude/skills and ~/.codex/skills, the
# ~/.local/bin links and the Codex allow rules. Only symlinks that point into this checkout are removed, so
# another installation's links stay; the rules stay too while any of its command links remain. Exact rule
# lines only; everything else stays. A peer-chat.py that install.sh moved aside stays as peer-chat.py.bak-<time>.
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
bin_dir="$HOME/.local/bin"
names=(
	"peer-chat-files.py"
	"peer-chat.py"
)
rules_file="$codex_home/rules/default.rules"
rules=(
	'prefix_rule(pattern=["peer-chat-files.py", "new"], decision="allow")'
	'prefix_rule(pattern=["peer-chat-files.py", "send"], decision="allow")'
	'prefix_rule(pattern=["peer-chat-files.py", "read"], decision="allow")'
)

if [ $# -gt 0 ]; then
	echo "usage: $0" >&2
	exit 2
fi

resolve() {
	python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

for link in "$HOME/.claude/skills/$(basename "$skill_dir")" "$codex_home/skills/$(basename "$skill_dir")"; do
	if [ -L "$link" ] && [ "$(resolve "$link")" = "$(resolve "$skill_dir")" ]; then
		rm "$link"
		echo "removed: $link"
	elif [ -L "$link" ]; then
		echo "skip: $link points to $(readlink "$link"), another installation; left as is" >&2
	elif [ -e "$link" ]; then
		echo "skip: $link is not a symlink, left as is" >&2
	else
		echo "absent: $link"
	fi
done

foreign_commands=0
for link in "${names[@]/#/$bin_dir/}"; do
	case "$link" in
		"$bin_dir/peer-chat-files.py") expected="$skill_dir/scripts/peer-chat.py" ;;
		*) expected="$skill_dir/scripts/peer-chat-typing.py" ;;
	esac
	if [ -L "$link" ] && [ "$(resolve "$link")" != "$(resolve "$expected")" ]; then
		echo "skip: $link points to $(readlink "$link"), another installation; left as is" >&2
		case "$link" in "$bin_dir"/*) foreign_commands=1 ;; esac
	elif [ -L "$link" ]; then
		rm "$link"
		echo "removed: $link"
	elif [ -e "$link" ]; then
		echo "skip: $link is not a symlink, left as is" >&2
	else
		echo "absent: $link"
	fi
done

if [ "$foreign_commands" = 1 ]; then
	echo "skip: Codex rules in $rules_file kept, another installation's commands still use them" >&2
elif [ -f "$rules_file" ]; then
	kept="$(mktemp "$rules_file.XXXXXX")"
	cp -p "$rules_file" "$kept"
	for rule in "${rules[@]}"; do
		if grep -Fxq -- "$rule" "$kept"; then
			grep -Fxv -- "$rule" "$kept" > "$kept.next" || true
			mv "$kept.next" "$kept"
			echo "rule removed: $rule"
		fi
	done
	mv "$kept" "$rules_file"
fi

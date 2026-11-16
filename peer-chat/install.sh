#!/usr/bin/env bash
# Links this skill folder into ~/.claude/skills and ~/.codex/skills, so both agents load the same SKILL.md. It never
# replaces a link to another installation or a real folder there: it checks both places first and stops before
# changing anything. Then links its scripts into ~/.local/bin, so every peer-chat command on PATH runs this skill's
# scripts and Codex's allow rules match them from any directory. A real file in the way in
# ~/.local/bin is moved aside as <name>.bak-<time>; any other peer-chat command on PATH is reported. The links point back here: edits need no reinstall, but moving the
# skill folder does (run this again from the new place).
# It also adds the Codex allow rules the commands need ($CODEX_HOME/rules/default.rules, default
# ~/.codex). Codex reads rules at startup, so restart it afterwards. uninstall.sh undoes both.
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
bin_dir="$HOME/.local/bin"
links=(
	"peer-chat-files.py:scripts/peer-chat.py"
	"peer-chat.py:scripts/peer-chat-typing.py"
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
skill_real="$(resolve "$skill_dir")"

skill_links=(
	"$HOME/.claude/skills/$(basename "$skill_real")"
	"$codex_home/skills/$(basename "$skill_real")"
)
for link in "${skill_links[@]}"; do
	if [ -L "$link" ] && [ "$(resolve "$link")" = "$skill_real" ]; then
		continue
	fi
	if [ -L "$link" ]; then
		echo "error: $link is a symlink to '$(readlink "$link")', another installation; remove it and rerun" >&2
		exit 1
	fi
	if [ -e "$link" ]; then
		echo "error: $link is a real directory or file, not a symlink; move it away and rerun" >&2
		exit 1
	fi
done
for link in "${skill_links[@]}"; do
	if [ -L "$link" ]; then
		echo "ok: $link -> $(readlink "$link")"
		continue
	fi
	mkdir -p "$(dirname "$link")"
	ln -s "$skill_real" "$link"
	echo "linked: $link -> $skill_real"
done

mkdir -p "$bin_dir"
for pair in "${links[@]}"; do
	link="$bin_dir/${pair%%:*}"
	target="$skill_dir/${pair#*:}"
	if [ ! -f "$target" ]; then
		echo "error: $target is missing" >&2
		exit 1
	fi
	if [ -e "$link" ] && [ ! -L "$link" ]; then
		backup="$link.bak-$(date +%Y%m%d-%H%M%S)"
		mv "$link" "$backup"
		echo "moved aside: $link -> $backup"
	elif [ -L "$link" ] && [ "$(resolve "$link")" != "$(resolve "$target")" ]; then
		echo "relinked: $link (was -> $(readlink "$link"))"
	fi
	chmod +x "$target"
	ln -sfn "$target" "$link"
	echo "linked: $link -> $target"
done

case ":$PATH:" in
	*":$bin_dir:"*) ;;
	*) echo "warning: $bin_dir is not on PATH; add it so the agents find the commands" >&2 ;;
esac

for pair in "${links[@]}"; do
	name="${pair%%:*}"
	first="$(command -v "$name" || true)"
	if [ -z "$first" ]; then
		echo "warning: $name is not found on PATH" >&2
	elif [ "$(resolve "$first")" != "$(resolve "$skill_dir/${pair#*:}")" ]; then
		echo "WARNING: $name on PATH is $first, which shadows $bin_dir/$name; put $bin_dir earlier in PATH" >&2
	fi
done

strays=()
seen=":"
IFS=: read -r -a path_dirs <<< "$PATH"
for folder in "${path_dirs[@]}"; do
	[ -d "$folder" ] || continue
	case "$seen" in *":$folder:"*) continue ;; esac
	seen="$seen$folder:"
	for command in "$folder"/peer-chat*; do
		[ -e "$command" ] || [ -L "$command" ] || continue
		case "$(resolve "$command")" in
			"$skill_real"/*) ;;
			*) strays+=("$command") ;;
		esac
	done
done
if [ ${#strays[@]} -gt 0 ]; then
	echo >&2
	echo "WARNING: these peer-chat commands on PATH do not point into $skill_dir:" >&2
	for command in "${strays[@]}"; do
		echo "  $command" >&2
	done
	echo "Remove them (backups included) or link them here, so every peer-chat command runs this skill." >&2
fi

mkdir -p "$(dirname "$rules_file")"
touch "$rules_file"
for rule in "${rules[@]}"; do
	if grep -Fxq -- "$rule" "$rules_file"; then
		echo "rule present: $rule"
	else
		[ -s "$rules_file" ] && [ -n "$(tail -c1 "$rules_file")" ] && echo >> "$rules_file"
		echo "$rule" >> "$rules_file"
		echo "rule added: $rule"
	fi
done
echo "Codex rules: $rules_file (restart Codex to load them)"

# Another peer-chat skill answers the same "Chat from …:" prompts, so an agent that sees both may load
# the wrong one. Links to this folder are not counted.
repo_root="$(git -C "$skill_dir" rev-parse --show-toplevel 2>/dev/null || true)"
v1_places=(
	"$HOME/.claude/skills/peer-chat"
	"$codex_home/skills/peer-chat"
	"$HOME/.agents/skills/peer-chat"
)
if [ -n "$repo_root" ]; then
	v1_places+=(
		"$repo_root/.claude/skills/peer-chat"
		"$repo_root/.agents/skills/peer-chat"
	)
fi
found=()
for place in "${v1_places[@]}"; do
	[ -e "$place/SKILL.md" ] || continue
	if [ "$(resolve "$place")" != "$skill_real" ]; then
		found+=("$place")
	fi
done
if [ ${#found[@]} -gt 0 ]; then
	echo >&2
	echo "WARNING: another peer-chat skill is installed too:" >&2
	for place in "${found[@]}"; do
		echo "  $place" >&2
	done
	echo "Both skills react to \"Chat from Claude:\" / \"Chat from Codex:\" prompts, so an agent may load the" >&2
	echo "wrong one. Remove or rename those you do not want, and make sure both panes use the same skill." >&2
fi

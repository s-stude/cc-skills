#!/usr/bin/env bash
# Make sure the other agent runs in the split pane of this agterm session, in this directory.
# Claude in this pane -> Codex in the other, and vice versa. Reuses a running peer, opens a split
# when there is none, and never touches a pane that runs something else.
#
# Usage: open-peer-pane.sh [--peer codex|claude] [--wait SECONDS]
# Prints one JSON line: {"status": "...", "peer": "...", "pane": "left|right", "cwd": "...", ...}
#   status: already-running | started | not-in-agterm | pane-busy | no-launch | start-timeout
# Exit 0 for already-running and started, 1 otherwise.

set -euo pipefail

peer=""
wait_s=60
while [ $# -gt 0 ]; do
  case "$1" in
    --peer) peer="$2"; shift 2 ;;
    --wait) wait_s="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$1"; }

if [ "${AGTERM_ENABLED:-}" != "1" ] || [ -z "${AGTERM_SESSION_ID:-}" ] || [ -z "${AGTERM_SOCKET:-}" ]; then
  say '{"status":"not-in-agterm"}'; exit 1
fi

ctl() { agtermctl "$@" --socket "$AGTERM_SOCKET"; }
cwd="$(pwd -P)"

# Facts about this session: which pane is mine, what each pane runs.
facts() {
  ctl tree --json | python3 -c '
import json, os, sys
tree = json.load(sys.stdin)
sid, me = os.environ["AGTERM_SESSION_ID"].lower(), os.environ.get("AGTERM_PANE_ID", "").lower()
def find(node):
    if isinstance(node, dict):
        if str(node.get("id", "")).lower() == sid and "surfaces" in node:
            return node
        node = list(node.values())
    if isinstance(node, list):
        for child in node:
            hit = find(child)
            if hit:
                return hit
s = find(tree) or {}
mine = next((x["kind"] for x in s.get("surfaces", []) if str(x.get("paneID", "")).lower() == me), os.environ.get("AGTERM_PANE", "left"))
other = "right" if mine == "left" else "left"
fg = lambda k: " ".join(s.get("foreground" if k == "left" else "splitForeground") or [])
shell = lambda k: s.get("foregroundShell" if k == "left" else "splitForegroundShell") or ""
other_id = next((x.get("paneID", "") for x in s.get("surfaces", []) if x.get("kind") == other), "")
print("\x1f".join([mine, other, "1" if s.get("hasSplit") else "0", fg(mine), fg(other), shell(other), other_id, s.get("splitCwd") or s.get("cwd") or ""]))
'
}

IFS=$'\x1f' read -r mine other has_split my_fg other_fg other_shell other_id split_cwd < <(facts)

if [ -z "$peer" ]; then
  case "$my_fg" in
    *codex*) peer=claude ;;
    *claude*) peer=codex ;;
    *) say "{\"status\":\"no-launch\",\"reason\":\"cannot tell which agent runs in this pane; pass --peer\"}"; exit 1 ;;
  esac
fi

if [ "$has_split" = "1" ]; then
  case "$other_fg" in
    *"$peer"*) say "{\"status\":\"already-running\",\"peer\":\"$peer\",\"pane\":\"$other\",\"cwd\":\"$split_cwd\"}"; exit 0 ;;
  esac
  if [ -n "$other_fg" ] || [ -z "$other_shell" ]; then
    say "{\"status\":\"pane-busy\",\"peer\":\"$peer\",\"pane\":\"$other\",\"running\":\"${other_fg//\"/}\"}"; exit 1
  fi
  ctl session split on --target "$AGTERM_SESSION_ID" >/dev/null
else
  ctl session split on --target "$AGTERM_SESSION_ID" >/dev/null
  for _ in $(seq 1 20); do
    IFS=$'\x1f' read -r mine other has_split my_fg other_fg other_shell other_id split_cwd < <(facts)
    [ -n "$other_shell" ] && break
    sleep 0.5
  done
  [ -n "$other_shell" ] || { say "{\"status\":\"no-launch\",\"reason\":\"split shell did not start\"}"; exit 1; }
fi

# The launch line runs in the user's interactive shell, so their own codex/claude wrappers apply.
line="cd $(printf '%q' "$cwd") && $peer"
if [ "$(ctl restore mode 2>/dev/null | sed -n 's/^this launch: .*active \([a-z]*\).*/\1/p')" = "live" ] && [ -n "$other_id" ]; then
  ctl session restart --target "$AGTERM_SESSION_ID" --pane-id "$other_id" --command "$line" >/dev/null
else
  # A fresh split shell at its prompt is the one place a typed launch line is safe.
  ctl session type --target "$AGTERM_SESSION_ID" --pane "$other" "$line"$'\n' >/dev/null
fi

deadline=$(( $(date +%s) + wait_s ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  IFS=$'\x1f' read -r mine other has_split my_fg other_fg other_shell other_id split_cwd < <(facts)
  case "$other_fg" in
    *"$peer"*) say "{\"status\":\"started\",\"peer\":\"$peer\",\"pane\":\"$other\",\"cwd\":\"$cwd\"}"; exit 0 ;;
  esac
  sleep 1
done
say "{\"status\":\"start-timeout\",\"peer\":\"$peer\",\"pane\":\"$other\"}"; exit 1

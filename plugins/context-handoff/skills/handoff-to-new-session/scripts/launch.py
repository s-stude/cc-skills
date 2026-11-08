#!/usr/bin/env python3
"""Opens a fresh agterm session next to this one, in the brief's directory, running Claude with the brief as its
appended system prompt, and recreates a peer program running in this session's split pane (Codex, say).

Usage: launch.py --brief .handoffs/brief-007.md [--task "short task"] [--no-peer] [--dry-run]

The new session gets HANDOFF_SEQ=007 from the brief's name, so peer-chat.py names its transcript
.peer-chats/chat-007.md.

Both the agterm session and the Claude session (claude --name) are named NNN-<task>-<project>, e.g.
007-handoff-naming-skills. The task comes from --task, else from the brief's "Task:" line under its goal; the
project is the name of the directory that holds .handoffs/.

Prints a JSON summary. Exits 1 when the new session's Claude cannot be confirmed running. Without agterm, prints
how to start the session by hand, with the brief's path, and exits 3."""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

SHELLS = { "zsh", "bash", "sh", "fish", "-zsh", "-bash" }

parser = argparse.ArgumentParser()
parser.add_argument("--brief", required=True)
parser.add_argument("--task", help="a few words naming the goal; overrides the brief's Task: line")
parser.add_argument("--no-peer", action="store_true", help="do not recreate the split pane's program")
parser.add_argument("--dry-run", action="store_true", help="print what would run, change nothing")
parser.add_argument("--agent", default="claude", help="the program to start (a test can pass a harmless one)")
args = parser.parse_args()

brief = Path(args.brief).resolve()
if not brief.is_file() or not brief.stat().st_size:
	sys.exit(f"brief is missing or empty: {brief}")
root = brief.parent.parent
relative_brief = brief.relative_to(root)
seq_match = re.fullmatch(r"brief-(\d{3,})\.md", brief.name)
if not seq_match:
	sys.exit(f"brief must be named brief-NNN.md (next-brief.sh reserves one): {brief.name}")
handoff_seq = seq_match.group(1)


def slug(text, limit):
	return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower()))[:limit].strip("-")


task = args.task
if not task:
	task_match = re.search(r"^Task:[ \t]*(.+)$", brief.read_text(), re.MULTILINE)
	task = task_match.group(1) if task_match else ""
task = slug(task, 40)
if not task or task.startswith("2-4-words"):
	sys.exit("name the task: add a 'Task: <2-4 words>' line under the brief's goal, or pass --task")
name = f"{handoff_seq}-{task}-{slug(root.name, 30) or 'project'}"

NO_AGTERM = 3
if not shutil.which("agtermctl"):
	reason = "agterm is not installed (no `agtermctl` on PATH)"
elif os.environ.get("AGTERM_ENABLED") != "1" or not os.environ.get("AGTERM_SOCKET") or not os.environ.get("AGTERM_SESSION_ID"):
	reason = "this Claude session is not running inside agterm"
else:
	reason = None
if reason:
	print(f"""Cannot open the new session automatically: {reason}.
The brief is written and ready: {brief}

Start the fresh session yourself:

  1. Open a new terminal window or tab.
  2. Run:
       cd {shlex.quote(str(root))}
       HANDOFF_SEQ={handoff_seq} claude --name {name}
  3. Send Claude this first message:
       Read {brief} and continue the work it hands over: start with its first steps.

Or as one command:

  cd {shlex.quote(str(root))} && HANDOFF_SEQ={handoff_seq} claude --name {name} --append-system-prompt "$(cat {shlex.quote(str(relative_brief))})" "Read {relative_brief} and continue the work it hands over: start with its first steps."

After the new session starts, stop editing files in this directory from this session, so only one session writes there.""")
	sys.exit(NO_AGTERM)

socket = os.environ["AGTERM_SOCKET"]
own_id = os.environ["AGTERM_SESSION_ID"]


def ctl(*command, stdin=None):
	result = subprocess.run([ "agtermctl", *command, "--socket", socket ], input=stdin, capture_output=True, text=True)
	if result.returncode:
		raise SystemExit(f"agtermctl {' '.join(command)} failed: {result.stderr.strip() or result.stdout.strip()}")
	return result.stdout.strip()


def find(session_id):
	tree = json.loads(ctl("tree", "--json"))
	found = []

	def walk(node):
		if isinstance(node, dict):
			if str(node.get("id", "")).lower() == session_id.lower() and ("realized" in node or "foreground" in node):
				found.append(node)
			for value in node.values():
				walk(value)
		elif isinstance(node, list):
			for value in node:
				walk(value)

	walk(tree.get("result", tree))
	return found[0] if found else None


def program(argv):
	return bool(argv) and Path(argv[0]).name not in SHELLS


if any(char in str(relative_brief) for char in "'\"$` "):
	sys.exit(f"brief path must be plain: {relative_brief}")
kickoff = f"Read {relative_brief} (also your appended system prompt) and continue the work it hands over: start with its first steps."
# The same shape start-branch uses: zsh -ic loads .zshrc, whose claude function ties Claude to this agterm session
command = f"zsh -ic 'export HANDOFF_SEQ={handoff_seq}; {args.agent} --name {name} --append-system-prompt \"$(cat {relative_brief})\" \"{kickoff}\"; exec zsh -l'"

own = find(own_id)
peer = None
if own and own.get("hasSplit") and program(own.get("splitForeground")) and not args.no_peer:
	peer = own["splitForeground"]

plan = { "cwd": str(root), "name": name, "handoffSeq": handoff_seq, "command": command, "peer": peer }
if args.dry_run:
	print(json.dumps({ "dryRun": True, **plan }, indent=2))
	sys.exit(0)

new_id = ctl("session", "new", "--after", own_id, "--no-select", "--cwd", str(root), "--name", name, "--command", command).splitlines()[-1].strip()

peer_line = None
if peer:
	ctl("session", "split", "on", "--target", new_id)
	for _ in range(40):
		node = find(new_id)
		if node and node.get("hasSplit") and node.get("splitForegroundShell"):
			break
		time.sleep(0.25)
	# A peer that was told this session's id (Codex's shell_environment_policy) must learn the new one
	peer_argv = [ part.replace(own_id, new_id).replace(own_id.lower(), new_id.lower()) for part in peer ]
	peer_line = shlex.join(peer_argv)
	ctl("session", "type", "--target", new_id, "--pane", "right", "--stdin", stdin=peer_line + "\n")

claude_ok = peer_ok = False
for _ in range(60):
	node = find(new_id) or {}
	claude_ok = Path(args.agent.split()[0]).name in " ".join(node.get("foreground") or [])
	peer_ok = not peer or program(node.get("splitForeground"))
	if claude_ok and peer_ok:
		break
	time.sleep(0.5)

print(json.dumps({ "session": new_id, "name": name, "brief": str(relative_brief), "handoffSeq": handoff_seq, "transcript": f".peer-chats/chat-{handoff_seq}.md", "claudeRunning": claude_ok, "peer": peer_line, "peerRunning": peer_ok if peer else None }, indent=2))
sys.exit(0 if claude_ok else 1)

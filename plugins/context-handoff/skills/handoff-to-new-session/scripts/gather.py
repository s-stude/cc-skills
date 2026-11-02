#!/usr/bin/env python3
"""Prints a Markdown snapshot of the facts a handoff brief needs: git state, this agterm session's panes and
processes, other sessions in the same directory, earlier briefs and peer transcripts. Read-only."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(*args, cwd=None):
	try:
		return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20).stdout.strip()
	except (OSError, subprocess.TimeoutExpired):
		return ""


def short(argv, limit=160):
	if not argv:
		return ""
	text = " ".join(" ".join(argv).split())
	return text if len(text) <= limit else text[:limit] + " …"


root = Path(sys.argv[1] if len(sys.argv) > 1 else (run("git", "rev-parse", "--show-toplevel") or os.getcwd())).resolve()
out = [f"# Handoff snapshot\n\n- Directory: `{root}`\n- Taken: {run('date', '+%Y-%m-%dT%H:%M:%S%z')}"]

if run("git", "rev-parse", "--git-dir", cwd=root):
	branch = run("git", "branch", "--show-current", cwd=root) or "(detached)"
	upstream = run("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", cwd=root)
	ahead = run("git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD", cwd=root) if upstream else ""
	out.append("\n## Git\n")
	out.append(f"- Branch: `{branch}`" + (f", upstream `{upstream}` (behind/ahead: {ahead})" if upstream else ", no upstream"))
	out.append(f"- HEAD: `{run('git', 'log', '-1', '--format=%h %s', cwd=root)}`")
	out.append(f"- Stash entries (shared across worktrees, do not pop): {len(run('git', 'stash', 'list', cwd=root).splitlines())}")
	status = run("git", "status", "--short", cwd=root)
	out.append("\n### Uncommitted changes\n\n```\n" + (status or "(clean)") + "\n```")
	out.append("\n### Recent commits\n\n```\n" + run("git", "log", "--oneline", "-20", cwd=root) + "\n```")
	worktrees = run("git", "worktree", "list", cwd=root)
	if len(worktrees.splitlines()) > 1:
		out.append("\n### Worktrees\n\n```\n" + worktrees + "\n```")

session_id = os.environ.get("AGTERM_SESSION_ID", "")
socket = os.environ.get("AGTERM_SOCKET")
if os.environ.get("AGTERM_ENABLED") == "1" and socket:
	tree_text = run("agtermctl", "tree", "--json", "--socket", socket, "--window", os.environ.get("AGTERM_WINDOW_ID", "active"))
	try:
		tree = json.loads(tree_text)
	except json.JSONDecodeError:
		tree = None
	sessions = []

	def walk(node, workspace=None):
		if isinstance(node, dict):
			if "sessions" in node and "name" in node:
				workspace = node.get("name")
			if "foreground" in node or "foregroundShell" in node or "realized" in node:
				sessions.append((workspace, node))
			for value in node.values():
				walk(value, workspace)
		elif isinstance(node, list):
			for value in node:
				walk(value, workspace)

	walk(tree)
	out.append("\n## agterm\n")
	for workspace, node in sessions:
		if node.get("id", "").lower() != session_id.lower():
			continue
		out.append(f"- This session: `{node.get('id')}` \"{node.get('name')}\" in workspace \"{workspace}\"" + (f", context \"{node['context']}\"" if node.get("context") else ""))
		out.append(f"- Main pane ({node.get('cwd')}): {short(node.get('foreground')) or 'shell ' + str(node.get('foregroundShell'))}")
		if node.get("hasSplit"):
			split = short(node.get("splitForeground")) or "shell " + str(node.get("splitForegroundShell"))
			out.append(f"- Split pane ({node.get('splitAxis')}, {'shown' if node.get('split') else 'hidden'}, {node.get('splitCwd')}): {split}")
		for key in ("overlay", "hud", "scratch", "status", "htmlOverlays", "paneOverlays"):
			if node.get(key):
				out.append(f"- {key}: {json.dumps(node[key], ensure_ascii=False)[:200]}")
	others = [
		(workspace, node) for workspace, node in sessions
		if node.get("id", "").lower() != session_id.lower() and str(root) in (node.get("cwd"), node.get("splitCwd"))
	]
	if others:
		out.append("\n### Other sessions in this directory (possible concurrent writers)\n")
		for workspace, node in others:
			out.append(f"- `{node.get('id')}` \"{node.get('name')}\" ({workspace}): main {short(node.get('foreground'), 80) or 'shell'}; split {short(node.get('splitForeground'), 80) or '-'}")
else:
	why = "agterm is not installed (no `agtermctl` on PATH)" if not shutil.which("agtermctl") else "this session is not inside agterm (`AGTERM_ENABLED` unset)"
	out.append(f"\n## agterm\n\n{why}: no panes to report, and the new session cannot be opened automatically. `launch.py` will print how to start it by hand.")

notes = []
seq = os.environ.get("HANDOFF_SEQ")
out.append("\n## Handoff chain\n")
out.append(f"- This session's number: {seq} (HANDOFF_SEQ)" if seq else "- This session's number: not set (HANDOFF_SEQ unset): the highest `.peer-chats/chat-NNN.md`, or 000")
out.append("- Briefs: `.handoffs/brief-NNN.md` (brief-NNN started session NNN); transcripts: `.peer-chats/chat-NNN.md` (session NNN's peer chat)")
for pattern in (".handoffs/brief-*.md", ".peer-chats/chat-*.md", ".handoff/brief*.md", ".claude/brief*.md", ".claude/system*.md", "*peer-chat*.md"):
	for path in sorted(root.glob(pattern)):
		if path.is_file() and path.stat().st_size:
			notes.append(f"- `{path.relative_to(root)}` ({path.stat().st_size} bytes, modified {run('date', '-r', str(int(path.stat().st_mtime)), '+%Y-%m-%d %H:%M')})")
if notes:
	out.append("\n## Earlier briefs, plans and transcripts\n\n" + "\n".join(notes))

print("\n".join(out))

#!/usr/bin/env python3
"""Peer chat through message files: the message lives in .peer-chats/chat-NNN/msg-NNN.md and only a
one-line pointer is typed into the other agent's pane (through the guarded text typing of peer-chat-typing.py beside it)."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

sys.dont_write_bytecode = True

PEER_DIR = ".peer-chats"
INDEX = "index.md"
MAX_MESSAGE_BYTES = 64 * 1024
SUBJECT_CHARS = 80
AGENTS = {"claude": "Claude", "codex": "Codex"}
SESSION_LINE = "- agterm session: "
CONVERSATION_RE = re.compile(r"^chat-(\d{3,})$")
TRANSCRIPT_FILE_RE = re.compile(r"^chat-(\d{3,})\.md$")
MESSAGE_FILE_RE = re.compile(r"^(msg-\d{3,})\.md$")
MESSAGE_ID_RE = re.compile(r"^msg-\d{3,}$")
ENTRY_RE = re.compile(
	r"^- (msg-\d{3,}) \| (\w+) → (\w+) \| (\w+) \| (\S+) \| sha256:(\S+) \| (.*)$"
)
FINAL_STATUSES = {"pending", "sent", "uncertain"}
TYPING_SCRIPT = "peer-chat-typing.py"


@dataclass(frozen=True)
class Entry:
	message_id: str
	sender: str
	recipient: str
	status: str
	stamp: str
	sha: str
	subject: str

	def line(self) -> str:
		return (
			f"- {self.message_id} | {self.sender} → {self.recipient} | {self.status} | "
			f"{self.stamp} | sha256:{self.sha} | {self.subject}"
		)


def now_stamp() -> str:
	return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def project_root() -> Path:
	try:
		top = subprocess.run(
			["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
		).stdout.strip()
		return Path(top)
	except (OSError, subprocess.CalledProcessError):
		return Path.cwd()


def other(agent: str) -> str:
	return next(name for name in AGENTS if name != agent)


def digest(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def subject(body: str) -> str:
	line = next((row for row in body.splitlines() if row.strip()), "")
	line = " ".join(line.lstrip().lstrip("#").replace("|", "/").split())
	if len(line) > SUBJECT_CHARS:
		line = line[: SUBJECT_CHARS - 1] + "…"
	return line


def exclude_from_git(root: Path) -> None:
	"""Keeps .peer-chats out of git through the local exclude file, never .gitignore."""
	try:
		ignored = subprocess.run(
			["git", "check-ignore", "-q", f"{PEER_DIR}/x"], cwd=root, capture_output=True
		)
		if ignored.returncode in (0, 128):
			return
		exclude = subprocess.run(
			["git", "rev-parse", "--git-path", "info/exclude"],
			cwd=root, capture_output=True, text=True, check=True,
		).stdout.strip()
	except (OSError, subprocess.CalledProcessError):
		return
	path = Path(exclude) if os.path.isabs(exclude) else root / exclude
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("a", encoding="utf-8") as stream:
		stream.write(f"{PEER_DIR}/\n")


def conversation_dir(root: Path, env: Mapping[str, str] | None = None) -> Path:
	"""The folder naming this agterm session, else HANDOFF_SEQ, else the next free number.
	Both peers share the session id, so whichever sends first creates the folder the other finds.
	Choosing and creating it happens under one lock, so two first sends cannot make two folders.
	Lock order: this lock, then an index lock."""
	base = root / PEER_DIR
	base.mkdir(parents=True, exist_ok=True)
	with (base / ".conversation.lock").open("a") as lock:
		fcntl.flock(lock, fcntl.LOCK_EX)
		return _conversation_dir(root, base, os.environ if env is None else env)


def _conversation_dir(root: Path, base: Path, environ: Mapping[str, str]) -> Path:
	session = environ.get("AGTERM_SESSION_ID", "").strip()
	numbers = []
	found = None
	if base.is_dir():
		for entry in sorted(base.iterdir()):
			folder = CONVERSATION_RE.match(entry.name)
			legacy = TRANSCRIPT_FILE_RE.match(entry.name)
			if folder and entry.is_dir():
				numbers.append(int(folder.group(1)))
				index = entry / INDEX
				if session and index.is_file() and f"{SESSION_LINE}{session}\n" in read_index_text(entry):
					found = entry
			elif legacy and entry.is_file():
				numbers.append(int(legacy.group(1)))
	if found:
		return found
	seq_text = environ.get("HANDOFF_SEQ", "").strip()
	if seq_text:
		if not seq_text.isdigit():
			raise ValueError(f"HANDOFF_SEQ must be a number, not {seq_text!r}")
		seq = int(seq_text)
	else:
		seq = max(numbers) + 1 if numbers else 0
	directory = base / f"chat-{seq:03d}"
	directory.mkdir(parents=True, exist_ok=True)
	exclude_from_git(root)
	index = directory / INDEX
	if not index.exists():
		brief = root / ".handoffs" / f"brief-{seq:03d}.md"
		header = [
			f"# Peer conversation {seq:03d}",
			"",
			f"{SESSION_LINE}{session or 'unknown'}",
			f"- started: {now_stamp()}",
			f"- brief: `.handoffs/brief-{seq:03d}.md`" if brief.exists() else "- brief: none",
			"",
			"One line per message: id | from → to | delivery | time | hash | subject.",
			"",
		]
		index.write_text("\n".join(header), encoding="utf-8")
	return directory


@contextmanager
def locked_index(directory: Path):
	with (directory / INDEX).open("r+", encoding="utf-8") as stream:
		fcntl.flock(stream, fcntl.LOCK_EX)
		yield stream


def parse_index(text: str) -> dict[str, Entry]:
	entries = {}
	for row in text.splitlines():
		match = ENTRY_RE.match(row)
		if match:
			entries[match.group(1)] = Entry(*match.groups())
	return entries


def read_index_text(directory: Path) -> str:
	"""Reads under a shared lock, so a reader never sees write_entry's truncated file."""
	with (directory / INDEX).open("r", encoding="utf-8") as stream:
		fcntl.flock(stream, fcntl.LOCK_SH)
		return stream.read()


def read_index(directory: Path) -> dict[str, Entry]:
	return parse_index(read_index_text(directory))


def write_entry(stream, entry: Entry) -> None:
	"""Replaces the entry's line, or appends it. The caller holds the lock."""
	stream.seek(0)
	rows = stream.read().splitlines()
	prefix = f"- {entry.message_id} |"
	at = next((i for i, row in enumerate(rows) if row.startswith(prefix)), None)
	if at is None:
		rows.append(entry.line())
	else:
		rows[at] = entry.line()
	stream.seek(0)
	stream.truncate()
	stream.write("\n".join(rows) + "\n")
	stream.flush()


def new_message(directory: Path, sender: str) -> tuple[str, Path]:
	with locked_index(directory) as stream:
		stream.seek(0)
		taken = [int(key[4:]) for key in parse_index(stream.read())]
		taken += [
			int(match.group(1)[4:])
			for match in (MESSAGE_FILE_RE.match(path.name) for path in directory.iterdir())
			if match
		]
		number = max(taken, default=0) + 1
		while True:
			message_id = f"msg-{number:03d}"
			path = directory / f"{message_id}.md"
			try:
				fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
			except FileExistsError:
				number += 1
				continue
			os.fchmod(fd, 0o600)
			os.close(fd)
			break
		write_entry(stream, Entry(message_id, AGENTS[sender], AGENTS[other(sender)], "draft", now_stamp(), "-", "-"))
	return message_id, path


def checked_body(path: Path) -> bytes:
	info = os.lstat(path)
	if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
		raise ValueError(f"{path.name} must be a regular file you own, with one link")
	if info.st_size > MAX_MESSAGE_BYTES:
		raise ValueError(f"{path.name} exceeds {MAX_MESSAGE_BYTES} bytes")
	data = path.read_bytes()
	text = data.decode("utf-8")
	if "\x00" in text:
		raise ValueError(f"{path.name} contains a NUL byte")
	if not text.strip():
		raise ValueError(f"{path.name} is empty; fill it before sending")
	return data


def send_message(
	root: Path,
	directory: Path,
	message_id: str,
	to: str,
	deliver: Callable[[str], int],
	phase: Callable[[], str] = lambda: "started",
) -> dict:
	"""Freezes the message file, records it, then types only its pointer line."""
	path = directory / f"{message_id}.md"
	with locked_index(directory) as stream:
		stream.seek(0)
		entry = parse_index(stream.read()).get(message_id)
		if entry is None:
			raise ValueError(f"{message_id} is not in {directory / INDEX}; create it with `new`")
		if entry.status in FINAL_STATUSES:
			raise ValueError(f"{message_id} is already {entry.status}; do not resend")
		if entry.sender == AGENTS[to]:
			raise ValueError(f"{entry.sender} wrote {message_id}; it goes to {entry.recipient}, not back")
		data = checked_body(path)
		os.chmod(path, 0o444)
		entry = replace(
			entry, status="pending", stamp=now_stamp(), sha=digest(data), subject=subject(data.decode("utf-8"))
		)
		write_entry(stream, entry)
	pointer = f"{message_id} {path.relative_to(root)} — {entry.subject}"
	try:
		deliver(pointer)
	except BaseException:
		status = "failed" if phase() == "not_started" else "uncertain"
		with locked_index(directory) as stream:
			write_entry(stream, replace(entry, status=status))
		raise
	with locked_index(directory) as stream:
		write_entry(stream, replace(entry, status="sent"))
	return {"sent": message_id, "path": str(path.relative_to(root)), "pointer": pointer}


def send_text(root: Path, directory: Path, sender: str, to: str, text: str, deliver, phase=lambda: "started") -> dict:
	message_id, path = new_message(directory, sender)
	path.write_text(text, encoding="utf-8")
	return send_message(root, directory, message_id, to, deliver, phase)


def read_message(root: Path, ref: str, env: Mapping[str, str] | None = None) -> str:
	if MESSAGE_ID_RE.match(ref):
		path = conversation_dir(root, env) / f"{ref}.md"
	else:
		raw = Path(ref)
		path = (raw if raw.is_absolute() else root / raw).resolve()
		peer_root = (root / PEER_DIR).resolve()
		inside = path.parent.parent == peer_root and CONVERSATION_RE.match(path.parent.name)
		if not inside or not MESSAGE_FILE_RE.match(path.name):
			raise ValueError(f"{ref} is not a peer-chat message (.peer-chats/chat-NNN/msg-NNN.md)")
	message_id = path.name[:-3]
	entry = read_index(path.parent).get(message_id)
	# pending is readable: the body is frozen and hashed before the pointer is typed, and the sender
	# may still be confirming delivery when the receiver acts on the pointer
	if entry is None or entry.status in ("draft", "failed"):
		status = entry.status if entry else "unlisted"
		raise ValueError(f"{message_id} is {status}, not sent")
	data = path.read_bytes()
	if digest(data) != entry.sha:
		raise ValueError(f"{message_id} changed after it was sent; ask {entry.sender} to send it again")
	delivery = "" if entry.status == "sent" else f" · delivery: {entry.status}"
	return f"{message_id} · {entry.sender} → {entry.recipient} · verified{delivery}\n\n{data.decode('utf-8')}"


def typing_script() -> Path:
	"""PEER_CHAT_TYPING, else the text-typing script bundled beside this one."""
	explicit = os.environ.get("PEER_CHAT_TYPING", "").strip()
	path = Path(explicit) if explicit else Path(__file__).resolve().with_name(TYPING_SCRIPT)
	if not path.is_file():
		raise RuntimeError(f"typing script not found at {path}")
	return path


def load_typing():
	script = typing_script()
	spec = importlib.util.spec_from_file_location("peer_chat_typing", script)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"peer-chat typing script not found at {script}")
	module = importlib.util.module_from_spec(spec)
	sys.modules["peer_chat_typing"] = module
	spec.loader.exec_module(module)
	if not hasattr(module, "send_with_retry"):
		raise RuntimeError(f"{script} is not the text-typing script (no send_with_retry)")
	return module


def pane_delivery(args: argparse.Namespace):
	typing = load_typing()
	profile = typing.target_profile(args.to, args.target_command, args.queue)
	window, sid = typing.resolve_target(args.session, args.window, profile)
	profile = typing.bind_pane(typing.find_node(sid, window), profile)
	progress = typing.DeliveryProgress()
	return (
		lambda line: typing.send_with_retry(sid, profile, line, window, progress),
		lambda: progress.phase,
	)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	commands = parser.add_subparsers(dest="command", required=True)

	new = commands.add_parser("new", help="reserve an empty message file and print its path")
	new.add_argument("--from", dest="sender", choices=AGENTS, required=True)

	send = commands.add_parser("send", help="freeze a filled message file and type its pointer")
	send.add_argument("message_id", nargs="?", help="msg-NNN from `new`")
	send.add_argument("--stdin", action="store_true", help="create the file from stdin and send it")
	send.add_argument("--to", choices=AGENTS, required=True)
	send.add_argument("--queue", action="store_true", help="Codex only: queue with Tab instead of steering")
	send.add_argument("--target-command", metavar="NAME")
	send.add_argument("--session")
	send.add_argument("--window")

	read = commands.add_parser("read", help="print a received message after checking its hash")
	read.add_argument("ref", help="the path from the pointer line, or msg-NNN")

	commands.add_parser("path", help="print this session's conversation folder")

	args = parser.parse_args(argv)
	if args.command == "send":
		if bool(args.stdin) == bool(args.message_id):
			parser.error("send takes either msg-NNN or --stdin")
		if args.message_id and not MESSAGE_ID_RE.match(args.message_id):
			parser.error("message id must look like msg-NNN")
		if args.queue and args.to != "codex":
			parser.error("--queue is available only with --to codex")
	return args


def run(args: argparse.Namespace) -> int:
	root = project_root()
	if args.command == "path":
		print(conversation_dir(root).relative_to(root))
		return 0
	if args.command == "read":
		sys.stdout.write(read_message(root, args.ref))
		return 0
	directory = conversation_dir(root)
	if args.command == "new":
		message_id, path = new_message(directory, args.sender)
		print(json.dumps({"id": message_id, "path": str(path.relative_to(root))}))
		return 0
	deliver, phase = pane_delivery(args)
	if args.stdin:
		text = sys.stdin.read(MAX_MESSAGE_BYTES + 1)
		result = send_text(root, directory, other(args.to), args.to, text, deliver, phase)
	else:
		result = send_message(root, directory, args.message_id, args.to, deliver, phase)
	print(json.dumps(result, ensure_ascii=False))
	return 0


def main() -> int:
	try:
		return run(parse_args())
	except KeyboardInterrupt as err:
		print(f"peer-chat: interrupted: {err or 'see the index for the delivery status'}", file=sys.stderr)
		return 130
	except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as err:
		print(f"peer-chat: {err}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())

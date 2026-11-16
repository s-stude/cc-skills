import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("peer_chat_files", HERE / "peer-chat.py")
chat = importlib.util.module_from_spec(spec)
sys.modules["peer_chat_files"] = chat
spec.loader.exec_module(chat)


class Root(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name)
		subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
		self.env = {"AGTERM_SESSION_ID": "S1"}

	def tearDown(self):
		for path in self.root.rglob("*"):
			if path.is_file():
				os.chmod(path, 0o600)
		self.tmp.cleanup()

	def conversation(self, env=None):
		return chat.conversation_dir(self.root, self.env if env is None else env)

	def draft(self, sender="codex", body="Subject line\n\nmore text\n"):
		directory = self.conversation()
		message_id, path = chat.new_message(directory, sender)
		path.write_text(body, encoding="utf-8")
		return directory, message_id, path


class ConversationTests(Root):
	def test_first_conversation_is_000_and_names_the_session(self):
		directory = self.conversation()
		self.assertEqual(directory.name, "chat-000")
		self.assertIn("- agterm session: S1\n", (directory / "index.md").read_text())

	def test_reuses_the_folder_that_names_this_session(self):
		first = self.conversation()
		self.conversation({"AGTERM_SESSION_ID": "S2"})
		self.assertEqual(self.conversation(), first)

	def test_session_folder_wins_over_handoff_seq(self):
		first = self.conversation()
		self.assertEqual(self.conversation({"AGTERM_SESSION_ID": "S1", "HANDOFF_SEQ": "7"}), first)

	def test_handoff_seq_names_a_new_folder(self):
		directory = self.conversation({"AGTERM_SESSION_ID": "S9", "HANDOFF_SEQ": "7"})
		self.assertEqual(directory.name, "chat-007")

	def test_next_free_number_counts_typed_chat_transcripts(self):
		(self.root / ".peer-chats").mkdir()
		(self.root / ".peer-chats" / "chat-003.md").write_text("# typed transcript\n")
		self.assertEqual(self.conversation().name, "chat-004")

	def test_folder_is_excluded_from_git(self):
		self.conversation()
		ignored = subprocess.run(["git", "check-ignore", "-q", ".peer-chats/x"], cwd=self.root)
		self.assertEqual(ignored.returncode, 0)


	def test_a_second_first_send_waits_and_finds_the_same_folder(self):
		other = None
		original = chat.exclude_from_git

		def start_the_other_peer(root):
			nonlocal other
			original(root)
			if other is None:
				code = (
					"import importlib.util, sys;"
					f"spec = importlib.util.spec_from_file_location('c', {str(HERE / 'peer-chat.py')!r});"
					"c = importlib.util.module_from_spec(spec); sys.modules['c'] = c; spec.loader.exec_module(c);"
					f"print(c.conversation_dir(__import__('pathlib').Path({str(self.root)!r}), {{'AGTERM_SESSION_ID': 'S1'}}).name)"
				)
				other = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
				time.sleep(0.5)

		chat.exclude_from_git = start_the_other_peer
		try:
			first = self.conversation()
		finally:
			chat.exclude_from_git = original
		out, err = other.communicate(timeout=10)
		self.assertEqual(out.strip(), first.name, err)
		self.assertEqual(sorted(p.name for p in (self.root / ".peer-chats").glob("chat-*")), ["chat-000"])


class NewTests(Root):
	def test_ids_are_sequential_private_and_listed_as_drafts(self):
		directory = self.conversation()
		first_id, first = chat.new_message(directory, "codex")
		second_id, _ = chat.new_message(directory, "claude")
		self.assertEqual((first_id, second_id), ("msg-001", "msg-002"))
		self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
		entry = chat.read_index(directory)["msg-001"]
		self.assertEqual((entry.sender, entry.status), ("Codex", "draft"))


class SendTests(Root):
	def test_send_freezes_the_file_and_types_only_the_pointer(self):
		directory, message_id, path = self.draft()
		typed = []
		result = chat.send_message(self.root, directory, message_id, "claude", lambda line: typed.append(line) or 1)
		self.assertEqual(typed, ["msg-001 .peer-chats/chat-000/msg-001.md — Subject line"])
		self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
		entry = chat.read_index(directory)[message_id]
		self.assertEqual(entry.status, "sent")
		self.assertEqual(entry.sha, chat.digest(path.read_bytes()))
		self.assertEqual(result["sent"], message_id)

	def test_a_sent_message_is_never_sent_again(self):
		directory, message_id, _ = self.draft()
		chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)
		with self.assertRaisesRegex(ValueError, "do not resend"):
			chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)

	def test_failure_before_typing_allows_a_retry(self):
		directory, message_id, _ = self.draft()

		def refuse(line):
			raise RuntimeError("prompt busy")

		with self.assertRaises(RuntimeError):
			chat.send_message(self.root, directory, message_id, "claude", refuse, lambda: "not_started")
		self.assertEqual(chat.read_index(directory)[message_id].status, "failed")
		chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)
		self.assertEqual(chat.read_index(directory)[message_id].status, "sent")

	def test_failure_after_typing_started_is_uncertain_and_final(self):
		directory, message_id, _ = self.draft()

		def break_midway(line):
			raise RuntimeError("submit unclear")

		with self.assertRaises(RuntimeError):
			chat.send_message(self.root, directory, message_id, "claude", break_midway, lambda: "started")
		self.assertEqual(chat.read_index(directory)[message_id].status, "uncertain")
		with self.assertRaisesRegex(ValueError, "do not resend"):
			chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)

	def test_empty_draft_is_refused(self):
		directory, message_id, _ = self.draft(body="  \n")
		with self.assertRaisesRegex(ValueError, "empty"):
			chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)

	def test_sending_to_yourself_is_refused(self):
		directory, message_id, _ = self.draft(sender="codex")
		with self.assertRaisesRegex(ValueError, "Codex wrote"):
			chat.send_message(self.root, directory, message_id, "codex", lambda line: 1)

	def test_oversize_draft_is_refused(self):
		directory, message_id, _ = self.draft(body="x" * (chat.MAX_MESSAGE_BYTES + 1))
		with self.assertRaisesRegex(ValueError, "exceeds"):
			chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)

	def test_stdin_send_creates_and_sends_in_one_step(self):
		directory = self.conversation()
		typed = []
		result = chat.send_text(self.root, directory, "claude", "codex", "# Review\n\n- one\n- two\n", lambda line: typed.append(line) or 1)
		self.assertEqual(typed, ["msg-001 .peer-chats/chat-000/msg-001.md — Review"])
		self.assertEqual((directory / "msg-001.md").read_text(), "# Review\n\n- one\n- two\n")
		self.assertEqual(result["sent"], "msg-001")


class SubjectTests(unittest.TestCase):
	def test_first_non_empty_line_without_heading_marks(self):
		self.assertEqual(chat.subject("\n\n## Timeout path |  still   fails\nbody"), "Timeout path / still fails")

	def test_long_subject_is_cut(self):
		self.assertEqual(len(chat.subject("a" * 300)), chat.SUBJECT_CHARS)


class ReadTests(Root):
	def sent(self):
		directory, message_id, path = self.draft()
		chat.send_message(self.root, directory, message_id, "claude", lambda line: 1)
		return directory, message_id, path

	def test_read_returns_header_and_body(self):
		_, _, path = self.sent()
		text = chat.read_message(self.root, ".peer-chats/chat-000/msg-001.md")
		self.assertTrue(text.startswith("msg-001 · Codex → Claude · verified\n\n"))
		self.assertTrue(text.endswith("Subject line\n\nmore text\n"))

	def test_read_by_id_uses_this_sessions_conversation(self):
		self.sent()
		self.assertIn("more text", chat.read_message(self.root, "msg-001", self.env))

	def test_changed_file_is_refused(self):
		_, _, path = self.sent()
		os.chmod(path, 0o600)
		path.write_text("something else\n")
		os.chmod(path, 0o444)
		with self.assertRaisesRegex(ValueError, "changed after it was sent"):
			chat.read_message(self.root, str(path))

	def test_pending_message_is_readable_while_the_sender_confirms_delivery(self):
		directory, message_id, path = self.draft()
		seen = []
		chat.send_message(
			self.root, directory, message_id, "claude",
			lambda line: seen.append(chat.read_message(self.root, str(path))) or 1,
		)
		self.assertTrue(seen[0].startswith("msg-001 · Codex → Claude · verified · delivery: pending\n\n"))
		self.assertTrue(chat.read_message(self.root, str(path)).startswith("msg-001 · Codex → Claude · verified\n\n"))

	def test_unsent_draft_is_refused(self):
		self.draft()
		with self.assertRaisesRegex(ValueError, "not sent"):
			chat.read_message(self.root, ".peer-chats/chat-000/msg-001.md")

	def test_path_outside_peer_chats_is_refused(self):
		(self.root / "msg-001.md").write_text("x")
		with self.assertRaisesRegex(ValueError, "not a peer-chat message"):
			chat.read_message(self.root, "msg-001.md/../msg-001.md")
		with self.assertRaisesRegex(ValueError, "not a peer-chat message"):
			chat.read_message(self.root, str(self.root / "msg-001.md"))


class TypingScriptTests(unittest.TestCase):
	def setUp(self):
		self.saved = os.environ.pop("PEER_CHAT_TYPING", None)

	def tearDown(self):
		os.environ.pop("PEER_CHAT_TYPING", None)
		if self.saved is not None:
			os.environ["PEER_CHAT_TYPING"] = self.saved

	def test_uses_the_bundled_script_even_through_a_symlink(self):
		with tempfile.TemporaryDirectory() as folder:
			link = Path(folder) / "peer-chat-files.py"
			link.symlink_to(HERE / "peer-chat.py")
			loaded = importlib.util.spec_from_file_location("peer_chat_linked", link)
			module = importlib.util.module_from_spec(loaded)
			sys.modules["peer_chat_linked"] = module
			loaded.loader.exec_module(module)
			self.assertEqual(module.typing_script(), HERE / "peer-chat-typing.py")
		self.assertTrue(hasattr(chat.load_typing(), "send_with_retry"))

	def test_override_must_exist(self):
		os.environ["PEER_CHAT_TYPING"] = "/nonexistent/peer-chat.py"
		with self.assertRaisesRegex(RuntimeError, "typing script not found"):
			chat.typing_script()


if __name__ == "__main__":
	unittest.main()

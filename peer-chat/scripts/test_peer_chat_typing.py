"""Tests of peer-chat-typing.py's transcript (the text-typing chat this skill types its pointers with)."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("peer_chat", Path(__file__).with_name("peer-chat-typing.py"))
peer_chat = importlib.util.module_from_spec(spec)
sys.modules["peer_chat"] = peer_chat
spec.loader.exec_module(peer_chat)


class TranscriptTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def path(self, **env):
        return peer_chat.transcript_path(self.root, env)

    def test_first_session_is_000_with_a_header(self):
        path = self.path(AGTERM_SESSION_ID="ABC")
        self.assertEqual(path, self.root / ".peer-chats" / "chat-000.md")
        text = path.read_text()
        self.assertIn("- agterm session: ABC\n", text)
        self.assertIn("- brief: none", text)

    def test_handoff_seq_names_the_file_and_links_its_brief(self):
        (self.root / ".handoffs").mkdir()
        (self.root / ".handoffs" / "brief-004.md").write_text("x")
        path = self.path(HANDOFF_SEQ="4", AGTERM_SESSION_ID="S4")
        self.assertEqual(path.name, "chat-004.md")
        self.assertIn("- brief: `.handoffs/brief-004.md`", path.read_text())

    def test_the_same_session_finds_its_file_again(self):
        first = self.path(AGTERM_SESSION_ID="ONE")
        second = self.path(AGTERM_SESSION_ID="TWO")
        self.assertEqual([ first.name, second.name ], [ "chat-000.md", "chat-001.md" ])
        self.assertEqual(self.path(AGTERM_SESSION_ID="ONE"), first)

    def test_a_bad_handoff_seq_is_refused(self):
        with self.assertRaises(ValueError):
            self.path(HANDOFF_SEQ="four")

    def test_ids_continue_across_files_and_from_the_legacy_transcript(self):
        (self.root / "peer-chat.md").write_text("### Codex → Claude · msg-047\n\nold\n")
        first = self.path(AGTERM_SESSION_ID="ONE")
        self.assertEqual(peer_chat.log_received(first, "Codex", "Claude", "hi"), "msg-048")
        second = self.path(AGTERM_SESSION_ID="TWO")
        typed = "Chat from Claude: next one"
        self.assertEqual(peer_chat.log_sent_pending(second, "Claude", "Codex", "Chat from Claude: ", typed), "msg-049")

    def test_a_sent_entry_starts_pending_and_records_the_typed_body(self):
        path = self.path(AGTERM_SESSION_ID="S")
        message_id = peer_chat.log_sent_pending(path, "Claude", "Codex", "Chat from Claude: ", "Chat from Claude: review abc please")
        text = path.read_text()
        self.assertIn(f"### Claude → Codex · {message_id}\n", text)
        self.assertIn("**Delivery:** pending", text)
        self.assertIn("_Whitespace collapsed and `Chat from Claude:` label added by peer-chat.py._", text)
        self.assertTrue(text.rstrip().endswith("review abc please"))
        peer_chat.set_delivery(path, message_id, "sent")
        self.assertIn("**Delivery:** sent", path.read_text())
        self.assertNotIn("pending", path.read_text())

    def test_set_delivery_touches_only_its_own_entry(self):
        path = self.path(AGTERM_SESSION_ID="S")
        one = peer_chat.log_sent_pending(path, "Claude", "Codex", "L: ", "L: one")
        two = peer_chat.log_sent_pending(path, "Claude", "Codex", "L: ", "L: two")
        peer_chat.set_delivery(path, two, "uncertain")
        text = path.read_text()
        self.assertLess(text.index("pending"), text.index("uncertain"))
        peer_chat.set_delivery(path, one, "failed")
        self.assertEqual(path.read_text().count("**Delivery:**"), 2)
        with self.assertRaises(ValueError):
            peer_chat.set_delivery(path, one, "sent")

    def test_received_is_verbatim_without_the_label(self):
        path = self.path(AGTERM_SESSION_ID="S")
        peer_chat.log_received(path, "Codex", "Claude", "Chat from Codex: Approved  a35c982c.\n")
        text = path.read_text()
        self.assertIn("### Codex → Claude · msg-001\n", text)
        self.assertIn("**Received:** ", text)
        self.assertTrue(text.rstrip().endswith("Approved  a35c982c."))
        with self.assertRaises(ValueError):
            peer_chat.log_received(path, "Codex", "Claude", "Chat from Codex:   ")

    def test_arguments(self):
        self.assertTrue(peer_chat.parse_args([ "--path" ]).path)
        args = peer_chat.parse_args([ "--log-received", "--from", "codex", "--stdin" ])
        self.assertEqual((args.log_received, args.sender), (True, "codex"))
        for bad in ([ "--log-received", "--stdin" ], [ "--path", "--to", "codex" ], [ "--to", "codex" ], [ "--stdin", "--from", "codex", "--to", "codex" ]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                peer_chat.parse_args(bad)
        self.assertTrue(peer_chat.parse_args([ "--to", "codex", "--stdin", "--no-log" ]).no_log)


class SendStatusTest(unittest.TestCase):
    """run_main around a stubbed delivery: the transcript's status must follow what delivery reported"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = peer_chat.transcript_path(Path(self.tmp.name), {"AGTERM_SESSION_ID": "S"})
        profile = peer_chat.PROFILES["codex"]
        for name, value in {
            "transcript_path": lambda *a, **k: self.path,
            "target_profile": lambda *a, **k: profile,
            "resolve_target": lambda *a, **k: (None, "S"),
            "find_node": lambda *a, **k: {},
            "bind_pane": lambda node, prof: prof,
            "read_message": lambda *a, **k: "please   review abc",
        }.items():
            patcher = mock.patch.object(peer_chat, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_send(self, delivery, argv=("--to", "codex", "--stdin")):
        progress = peer_chat.DeliveryProgress()
        with mock.patch.object(peer_chat, "send_with_retry", lambda sid, prof, message, window, prog: delivery(prog)), \
                mock.patch.object(sys, "argv", ["peer-chat.py", *argv]), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                return peer_chat.run_main(progress), progress
            except BaseException as err:  # noqa: BLE001 - the test inspects what escaped
                return err, progress

    def status(self):
        return [ line for line in self.path.read_text().splitlines() if line.startswith("**Delivery:**") ]

    def test_a_confirmed_delivery_is_sent_with_the_typed_text(self):
        result, _ = self.run_send(lambda progress: 21)
        self.assertEqual(result, 0)
        self.assertEqual(self.status(), [ "**Delivery:** sent  " ])
        self.assertTrue(self.path.read_text().rstrip().endswith("please review abc"))

    def test_a_refusal_before_typing_is_failed(self):
        def refuse(progress):
            raise peer_chat.PromptBlocked("composer busy")
        result, _ = self.run_send(refuse)
        self.assertIsInstance(result, peer_chat.PromptBlocked)
        self.assertEqual(self.status(), [ "**Delivery:** failed  " ])

    def test_a_failure_after_typing_began_is_uncertain(self):
        def broke(progress):
            progress.phase = "started"
            raise RuntimeError("submit not accepted")
        result, _ = self.run_send(broke)
        self.assertIsInstance(result, RuntimeError)
        self.assertEqual(self.status(), [ "**Delivery:** uncertain  " ])

    def test_an_interrupt_after_typing_began_is_uncertain(self):
        def interrupted(progress):
            progress.phase = "started"
            raise KeyboardInterrupt
        result, _ = self.run_send(interrupted)
        self.assertIsInstance(result, KeyboardInterrupt)
        self.assertEqual(self.status(), [ "**Delivery:** uncertain  " ])

    def test_the_entry_is_written_before_delivery_starts(self):
        seen = []
        def look(progress):
            seen.append(self.status())
            return 5
        self.run_send(look)
        self.assertEqual(seen, [ [ "**Delivery:** pending  " ] ])

    def test_no_log_writes_nothing(self):
        before = self.path.read_text()
        result, _ = self.run_send(lambda progress: 5, ("--to", "codex", "--stdin", "--no-log"))
        self.assertEqual(result, 0)
        self.assertEqual(self.path.read_text(), before)


if __name__ == "__main__":
    unittest.main()

---
name: handoff-to-new-session
description: Hand the current session's work over to a fresh Claude session in a new agterm session on the same directory, through a numbered brief in .handoffs/brief-NNN.md that captures the goal, the rules, what is done, what remains, the decisions made, the workflow, and the panes, peers and processes in use. Use whenever the user wants to continue the work with a fresh context or in another session ("hand off", "handoff", "continue in a new session", "start a fresh session with this context", "pass this on to a new agent", "my context is getting long, move to a new session", "open another session to carry on the same way"), or invokes /context-handoff:handoff-to-new-session, even if they don't name the skill. Not for starting unrelated new work on its own branch (that is start-branch).
---

# Handoff to a new session

The point is a fresh context that loses nothing that matters. The new session sees only the brief and the
files on disk, not this conversation. A brief that leaves out the goal, a rule, or the state of the task in
progress makes the new session guess, redo work, or break a constraint the user set hours ago. Writing the
brief is the real work; the scripts below handle the rest.

`<skill-dir>` below is the directory this SKILL.md was loaded from (its base directory), not the working
directory.

## 1. Snapshot the facts

```bash
python3 <skill-dir>/scripts/gather.py
```

It prints, read-only:
- git state: branch, HEAD, uncommitted changes, recent commits, worktrees;
- this agterm session: its panes and what runs in them;
- other sessions in the same directory;
- the handoff chain: this session's number (`HANDOFF_SEQ`), earlier briefs (`.handoffs/brief-NNN.md`) and
  peer transcripts (`.peer-chats/chat-NNN.md`), plus the old `.handoff/` and `peer-chat.md` if present.

Treat the output as raw material for the Environment and Done sections, not as the brief.

Look at the "Other sessions in this directory" list. If one of them is writing here too, the new session
must not become a second writer behind the user's back. Say so in the brief, and ask the user if it is
unclear who writes.

## 2. Reserve the brief file

```bash
<skill-dir>/scripts/next-brief.sh      # prints e.g. /path/to/repo/.handoffs/brief-004.md
```

Briefs and transcripts form one numbered chain per worktree: `.handoffs/brief-NNN.md` is what starts
session NNN, and `.peer-chats/chat-NNN.md` is session NNN's peer conversation (the peer-chat script names it
from `HANDOFF_SEQ`). The first session of a worktree, which had no brief, is 000. So the next brief's number
is one past the highest brief or transcript: the session writing it is the highest so far.

The script creates `.handoffs/` in the git top level (or the working directory), takes that number, and
creates the file empty so the number is held. It also keeps `.handoffs/` and `.peer-chats/` out of git
through the repository's local `info/exclude`; it never edits `.gitignore`. Briefs are working notes, not
project history. Briefs are not named after the agterm session: the new session's id is not known yet when
the brief is written. An old `.handoff/briefNNN.md` folder is left where it is.

## 3. Write the brief

Use the template in `references/brief-template.md` and fill every section. What decides its quality:

- **The goal first, in the user's words.** Start the section with a `Task:` line of 2-4 words naming
  the goal; it becomes the new session's name. Quote the requests that define the work, verbatim and in order,
  then say what "done" means. With the goal right, the new session can recover from almost any other gap.
- **Rules and constraints.** List every standing instruction still in force: what must not change, gates,
  conventions, corrections the user made. Corrections are the easiest to lose and the costliest to repeat.
- **Done, with evidence.** Give commit hashes, files and passing commands, so the reader can check rather
  than trust. Include dead ends and why they failed.
- **What remains, concrete and ordered.** For each task, say where it lives, how to tell it is done, and any
  known trap. Describe the task in progress precisely: how far it got and which uncommitted changes belong
  to it.
- **Decisions and knowledge.** Record the choices made, the alternatives rejected, and the facts learned the
  hard way. This is the part a fresh session cannot rebuild cheaply.
- **The workflow.** Cover the build, test and review loop, commit habits, and transcripts and who keeps
  them.
- **Environment.** Cover panes, peers, long-running processes and other sessions, from the snapshot, edited
  down.

- **Traps hit this session.** Every behaviour that cost more than one try (a tool's quirk, an ordering
  rule, a misleading error), each in one line with the fix. Put the lasting ones in the project's docs too
  (a plan's decisions section, a harness doc) and point to them: a brief is read once, the docs every time.
- **The peer's first message.** A new peer starts with no memory. Write the exact first message the new
  session sends it: the roles, the files to read, and any review still waiting.

Write for a reader with no memory of this conversation. Never write "as discussed" or "the earlier
approach"; name the thing. Point to files instead of pasting their contents. Quote exact commands. Aim for
something a capable engineer could act on after one careful read; 100-300 lines is typical. Leave out
secrets: the brief is passed on a command line and stays on disk.

Don't commit, push, stash or clean up as part of a handoff unless the user asked. Record the state as it is,
uncommitted changes included, and say whose they are.

## 4. Open the new session

**Launch as soon as the brief is ready**, without asking, unless the user said in this session to wait or to
start it themselves (then stop with the brief ready and say how to start it). Check that the brief is
complete first: once the session runs, its first message is already sent.

```bash
python3 <skill-dir>/scripts/launch.py --brief .handoffs/brief-NNN.md
```

What it does:
- opens a new agterm session right after this one, without switching the user to it, in the directory
  that holds `.handoffs/`;
- names it, and the Claude session in it (`claude --name`), `NNN-<task>-<project>`, e.g.
  `013-handoff-naming-skills`: the number from the brief, the task from the brief's `Task:` line, the
  project from the directory name;
- starts `claude` there with `HANDOFF_SEQ=NNN` (from the brief's name, so its peer transcript is
  `.peer-chats/chat-NNN.md`), the brief as its appended system prompt, and a first message that points it at
  the brief file;
- if this session's split pane runs a program (a peer such as Codex), opens a split in the new session and
  starts the same command there, with this session's id swapped for the new one, so a peer that was told
  its agterm session id talks to the right pane;
- waits until both are running and prints a JSON summary.

Use `--no-peer` when the peer should not follow, and `--dry-run` to see the commands first. `--agent CMD`
replaces `claude` (a test can pass `"sleep 30 #"`).

The `Task:` line under the brief's goal names the session: 2-4 words taken from the goal, e.g.
`Task: handoff naming`. The user reads the name in the agterm sidebar and in the Claude session list, so
name the goal, not the handoff. `--task "..."` overrides the line.

### Without agterm

Opening the new session needs [agterm](https://agterm.com), the terminal app, and this
session running inside it. When agterm is not installed (no `agtermctl` on PATH) or this session is not in
it (`AGTERM_ENABLED` unset), still do steps 1–3: the brief is the handoff, agterm only opens the window. Then
run `launch.py` as above anyway: it opens nothing, prints why and the manual steps with the brief's
absolute path, and exits 3. Exit 3 is the expected outcome here, not a failure to retry or work around.

Show the user that output in full, as is, in your reply. Don't summarize it or leave it in the tool result
alone, because the user can't see tool output. It tells them to:
1. open a new terminal in the project directory;
2. run `HANDOFF_SEQ=NNN claude --name NNN-<task>-<project>`;
3. ask Claude to read the brief, by its absolute path, and continue;

and gives the same as one `claude --append-system-prompt …` command. Say plainly that agterm is missing (or
not in use), so the new session could not be opened for them, and that installing agterm (https://agterm.com) makes this
automatic next time.

## 5. Verify, step back, report

- Without agterm (`launch.py` exited 3), skip the checks below that need a running session: your report
  is the manual steps from "Without agterm", with the brief's absolute path.
- Check the summary: `claudeRunning` and, if a peer was started, `peerRunning` should be `true`. If the
  peer's pane shows a trust or permissions prompt, tell the user; never answer it for them.
- From now on this session writes nothing in that directory. The new session is the writer, and two
  writers in one checkout collide. This session can still answer questions or review.
- If a peer in this session's split pane was part of the work, it may help to tell it that the work moved,
  so it does not keep reviewing here. Its own instructions decide whether it listens; that is not required.
- Tell the user, briefly: the new session's name, the brief's path, what it will do first, and anything left
  open (an unanswered prompt, uncommitted changes, a process left running). Mention that they can close
  this session when they are done with it.

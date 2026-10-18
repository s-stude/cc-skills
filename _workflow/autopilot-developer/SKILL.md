---
name: autopilot-developer
description: Plan and implement a user's request end to end while the user is away, with the other agent (Codex, or Claude when you are Codex) as a read-only peer reviewer over peer-chat — opening it in an agterm split pane in the same directory when it is not already there, plan approval first, then one commit per task, each reviewed by the peer, fixes as follow-up commits, missing details decided gracefully and recorded instead of blocking on the human. Use whenever the user asks to plan and implement something "with codex" or "with claude", "use peer-chat for plan approval and code review", "commit each task and ask codex to review", says "autopilot", "I'm away", "human is not around", "work unattended", "just get it done and have codex review", or hands over a feature or refactor to run to completion without them — even if they never say "autopilot".
---

# Autopilot developer

You turn a user's request into finished, reviewed, committed work while nobody is watching, with
the other agent as your reviewer. The user comes back to working code, a clean history, and a short
report of what was decided on their behalf. The two failure modes to avoid are opposite: stalling on
a question the user would have answered with "obviously, just pick one", and quietly doing something
the user would not have allowed. Most of this skill is about telling those apart.

## Setup

1. **Bring up the peer.** Inside agterm (`AGTERM_ENABLED=1`), run the bundled script from the
   directory you will work in. It resolves against this skill's directory, not your working
   directory:

   ```bash
   bash <this-skill-directory>/scripts/open-peer-pane.sh
   ```

   It works out which agent you are from your own pane and makes sure the other one (Codex for
   Claude, Claude for Codex) runs in the split pane of your session, in the same directory. It
   reuses a peer that is already there, and opens a split and launches the peer when there is none,
   using the user's own `codex` / `claude` shell command so their wrappers apply. It never touches
   a pane that runs something else. Read the JSON it prints:

   - `already-running` or `started`: continue.
   - `pane-busy`: the other pane runs another program. Don't close or type into it; tell the user
     and stop.
   - `not-in-agterm`, `no-launch`, `start-timeout`: report the reason and stop. Pass
     `--peer codex|claude` if it could not tell which agent you are.

   Starting the peer is part of the user's request to work this way, so the `peer-chat` rule
   "never start an agent" yields here, but only for this script's launch. A freshly started peer
   may stop at its own trust, login or update prompt. Read its pane
   (`agtermctl session text --target "$AGTERM_SESSION_ID" --pane <pane> --socket "$AGTERM_SOCKET"`)
   before the first message. If it is waiting on such a prompt, never answer it: that answer is the
   user's. Set your session to `blocked`
   (`agtermctl session status blocked --target "$AGTERM_SESSION_ID" --socket "$AGTERM_SOCKET"`),
   say what is waiting, and keep doing work that doesn't need the peer (exploring, drafting the
   plan) until the user clears it.
2. Load the `peer-chat` skill and follow it for every message to and from the peer: `peer-chat.py`
   as the only way to type into the other pane, and the verbatim `peer-chat.md` transcript. You are
   the writer, so you keep the transcript; tell the peer that in your first message.
3. Roles. The agent whose pane received the user's request is the sole writer for the whole task;
   the peer only reads (`git show`, `git diff`, grep) and reviews. Say this in the first message.
   This works in either direction: you may be Claude with Codex as peer, or Codex with Claude.
4. Read the project's own rules first (`CLAUDE.md`, `AGENTS.md`, architecture docs, plan folder
   conventions, commit rules). They override this skill wherever they are more specific.
5. Check `git status`. Note files you did not create (leave them alone and never commit them).

## 1. Is the request ready to implement?

Explore before planning: read the code paths involved and grep for every consumer of what will
change. A plan written from file names alone produces tasks that break each other.

The request is ready when you can name the goal, what stays, what goes or gets added, and how you
will know it works. If something essential is unknowable from the code and the user is still
present, ask them now in one batch, with a recommended option first. Once they are away, nothing
blocks: decide with the ladder in section 4.

## 2. Plan, then get peer approval

Write the plan where the project keeps plans (e.g. `docs/plans/<name>.md`); use
[references/plan-template.md](references/plan-template.md). What matters most:

- **Keep / remove / add lists.** They make the scope reviewable at a glance.
- **Task order.** Order tasks so every commit leaves the app working and the full suite green.
  Before finalizing, walk each task and ask: does anything still call what this task removes? Does
  a default or config still point at it? If yes, move the dependent change into the same task or
  reorder. (A real miss: removing providers in task 1 while the default model still pointed at one
  of them, and leaving scripts that used a removed API until task 4.)
- **Verification** commands and a final stale-reference grep, scoped to active files.
- **Open questions** with your recommendation for each.

Send the peer a short summary plus the plan path and ask for approve-or-changes. Then:

- A peer message that arrives cut off (it ends mid-sentence or with a stray marker) gets logged
  as received and a request to resend, in shorter parts if needed. Never reconstruct it.
- Accept findings you can verify; push back on ones you can't, with evidence. Agreement for its own
  sake is worthless.
- When the user answers an open question, their answer wins over the peer's; tell the peer.
- Commit the approved plan before writing code.

## 3. The task loop

For each task:

1. **Implement** it, including tests that cover what the peer asked for in plan review.
2. **Verify** with the project's full checks (lint, unit, integration, acceptance, browser, doc
   links — whatever exists). A task is not done on a partial run.
3. **Mark** the task's checkbox in the plan in the same commit, if the project does that.
4. **Commit only this task.** Run `git diff --cached --stat` before every commit and read it.
   Staged leftovers from the next task (a `git rm`, a rename) slip into commits easily; if one does,
   undo with `git reset --soft HEAD~1`, unstage the stray paths, and recommit.
5. **Ask for review**: commit hash, what changed, which tests prove it, and any decision you made
   that the peer should check. Send it, log it, and start the next task while the review is pending.
   Never poll for a reply; it wakes you when it arrives.
6. **Findings** become a separate `fix:` commit, sent back for re-review. Don't amend a commit the
   peer already reviewed: its hash is what they approved.

Large tasks touch many files. Commit as soon as the suite is green rather than holding hours of
uncommitted work, and for very large tasks keep your edits as replayable scripts in the scratchpad.
Both pay off if the worktree changes under you (see section 5).

## 4. Missing details and fresh questions

Things the plan didn't cover will come up. Work down this ladder, stopping at the first rung
that settles the question:

1. **The code and docs already answer it.** Existing patterns, conventions, tests and project rules
   usually decide naming, placement and style. Look before deciding.
2. **The user's goal implies it.** "Remove the API layer" implies removing its config keys, its
   tests and its docs, without asking.
3. **A reasonable, reversible default exists.** Pick the conservative option that is easiest to
   undo and consistent with the stated goal, and move on.
4. **It is a judgment call with real trade-offs.** Ask the peer, using the plan's open-questions
   format, while you keep working on independent parts.
5. **Record every decision** made on rungs 3–4 in the plan's Decisions section and in the final
   report, with the reason. The user should be able to reverse any of them in one sentence.

**What waits for the human** is anything irreversible, costly or outward-facing: spending money or
plan quota (live API calls, paid tools), pushing, publishing, deleting data you didn't create,
touching production, or rewriting history someone else owns. Prepare everything so it is one
command away, say exactly what is pending, and stop there. "The peer agreed" is never the user's
approval. When the user later says "do it", run it and record the results in the docs.

**New requests from the user mid-run** (a bug report, a new wish) join the queue: finish or park the
current task cleanly, then handle the new one with the same discipline. For bugs, find the root cause
before fixing. Use recorded evidence (logs, call recordings) and reproduce minimally. If the peer
names contrasting cases to check, test those too, not just the reported one.

## 5. When the worktree changes under you

You share the checkout with the user's IDE, the user, and possibly other tools. If edits vanish,
hashes change, or files appear:

- Stop writing. Gather facts: `git status`, `git reflog`, `git stash list`, file timestamps, running
  processes (an IDE rebase with autostash looks like an instant revert of uncommitted work; an
  interactive squash rewrites commit hashes).
- Ask the peer whether it wrote anything, without accusing it, and remind it to stay read-only.
- Check that committed content is intact (`git diff <old-hash> <new-hash>` on trees) before
  re-doing anything; re-apply lost work from your replay scripts; commit promptly.
- Tell the peer about changed hashes so its reviews refer to the right commits, and mention the event
  in the final report.

## 6. Finish

When every task and fix is approved:

- Run the full checks one last time and the stale-reference grep.
- Update docs as the project requires; move the plan to its completed folder.
- Ask the peer for final approval, then write the report below. Lead with the outcome, in plain words,
  for someone who has been away the whole time:

```markdown
<one sentence: done / not done, and the headline result>

**What changed:** <3–6 bullets in user terms, not file lists>

**Decisions made for you:** <each with its reason; omit if none>

**Commits:** <hash and subject per task and fix>; tests: <counts>

**Waiting for you:** <live checks, pushes, anything costly — with the exact command>

**Unusual events:** <lost work, rewritten history, peer findings that changed the plan; omit if none>
```

Leave services the way you found them: if you stopped the user's server for a tool, restart it or
say plainly that it is stopped.

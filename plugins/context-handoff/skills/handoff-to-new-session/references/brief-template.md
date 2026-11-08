# Brief template

Fill every section, or write "none" so the reader knows it was checked. A section that only says "see the
conversation" is a missing section. Paths are repo-relative or absolute, commits are short hashes, and every
claim is something the reader can check.

```markdown
# Handoff NNN: <one line naming the work>

You take over work another session started in this directory. That session stops writing once you start:
**you are the only writer here now.** <Anything to run first, such as `bun install`.>

- Directory: `<absolute path>`
- Branch: `<branch>` (base `<base>`), HEAD `<hash> <subject>` when this was written
- Handed over from: agterm session `<id>` ("<name>"), <date and time with zone>
- Earlier briefs: `<paths, oldest first>`, or none
- Previous peer transcript: `.peer-chats/chat-<NNN-1>.md`, or none. Yours will be `.peer-chats/chat-NNN.md`.

## The goal

Task: <2-4 words naming the goal, e.g. "handoff naming"; launch.py names the sessions NNN-<task>-<project> from it>

<The user's requests that define the work, verbatim, in order, each quoted. Then two or three sentences on
what "done" means and why the user wants it. This section matters most: a session that knows the goal can
recover from any other gap in the brief.>

## Rules and constraints

<Every standing instruction from the user or the project that applies, with its reason when it was given:
what must not change, review or approval gates, commit conventions, style rules. Quote the user where the
wording matters.>

## Done so far

<What is finished, each item with its evidence: a commit hash, a file, a passing command. Mention what was
tried and abandoned, and why, so it is not tried again.>

## What remains

<Ordered, concrete tasks. For each one: what to do, where (files, functions), how to tell it is done (a
command, a test, an observable result), and any known trap. Mark the one in progress and how far it got,
including uncommitted changes and whose they are.>

## Decisions and knowledge

<Choices made along the way and why (option chosen, options rejected). Facts learned the hard way: how a
tool really behaves, a misleading name, a test that only passes when run alone, a helper that already
exists. Things the reader would otherwise rediscover at a cost.>

## Traps hit

<One line each: what cost more than one try, and what to do instead (an ordering rule, a tool quirk, a
misleading error). Point to where the lasting ones are written in the project's docs.>

## How the work runs

<The working loop: build, test and lint commands and when to run them, how commits are made, how reviews
happen, where notes and transcripts go and who keeps them.>

## The peer's first message

<If a peer pane comes along: the exact first message to send it with the peer-chat script, which starts
with no memory. The roles (who writes, who reviews read-only, who keeps the transcript), the files to read,
and any review still waiting, with its commits. "None" when there is no peer.>

## Environment

<From the snapshot (`scripts/gather.py`), edited down to what matters: panes and what runs in them, peers
and how to reach them, long-running processes (dev servers, watchers, background jobs) with how to find,
reuse or stop them, other sessions in the same directory and what they may write.>

## Open questions

<Questions waiting for the user, and decisions the reader must not make alone. "None" when there are none.>

## Read first

<Files to read before acting, in order, each with one line on why.>

## First steps

<What to do in the first minutes: read the files above, check that the state matches this brief (`git
log`, `git status`, tests), report a short summary of the situation and the plan to the user, then start
the first remaining task.>
```

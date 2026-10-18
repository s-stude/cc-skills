---
name: start-branch
description: Start new work in its own branch and sibling worktree - name the branch airesearch-worktree-<name>, add the worktree at ../roadmap-worktree-<name>, write a brief, and open a new Claude session there in agterm. Use whenever the user asks for development work (a feature, fix, refactor, tests, a docs change), asks to start, open or spin up a branch or worktree, or asks to run an existing branch in a separate worktree, even if they don't name the skill. The root session hands the work off instead of doing it itself.
---

# Start branch

Development work doesn't happen in the root session. The repo root stays checked out on `airesearch`, the baseline, and each piece of work gets its own branch, its own worktree folder next to the repo, and its own Claude session in agterm. That keeps parallel work isolated and lets each session resume after a restart.

Questions, explanations, reviews and git housekeeping (merging back, cleanup) stay in the root session. So does work the user explicitly asks to do here. Merging back goes through the `finish-branch` skill.

## Naming and placement

Pick a short kebab-case `<name>` that describes the work, such as `usecases-split` or `entrance-e2e`.

| What | Pattern | Example |
| --- | --- | --- |
| Branch | `airesearch-worktree-<name>` | `airesearch-worktree-usecases-split` |
| Worktree folder | `../roadmap-worktree-<name>`, a sibling of the repo root | `roadmap-oct-2026/roadmap-worktree-usecases-split` |
| agterm session | `<name>` | `usecases-split` |

The base is `airesearch` unless the user names another one.

Worktrees don't go under `.claude/worktrees/`. That was the old location, as were the names `roadmap-<name>` and `airesearch-<name>`. Older branches and worktrees may still use them; leave them as they are unless the user asks.

## Steps

### 1. Check before creating anything

Run all the checks first and create nothing until every one passes. A half-failed `git worktree add` is messy: when the folder already exists, git refuses the worktree but still creates the branch, leaving a stray branch behind.

```bash
git branch --list airesearch-worktree-<name>          # local branch
git branch -r --list '*/airesearch-worktree-<name>'   # branch on a remote
test -e ../roadmap-worktree-<name> && echo exists      # folder on disk
git worktree list --porcelain                          # worktree registered at that path, even if its folder is gone
```

If the branch exists (locally or on a remote), or the folder exists, or a worktree is registered at that path, **stop and report**. Don't reuse, move, rename, prune, force or delete anything. The user decides whether to reuse the branch or the folder, or to pick another name. The report says:

- which check failed: branch (local or remote), folder, or registered worktree
- for a branch: its last commit (`git log -1 --oneline <branch>`), how far ahead of `airesearch` it is, and where it is checked out (`git worktree list`)
- for a folder: whether it is a worktree and which branch it is on, or whether it is an ordinary folder
- for a registered worktree whose folder is gone: that `git worktree prune` would clear it

Then wait for the user's answer and continue with what they choose.

**Running an existing branch.** When the user explicitly asks to run a branch that already exists, that request is their decision to reuse the branch, so the branch check doesn't stop you. Still run the folder and worktree checks:

- Name the folder after the branch: `<name>` is the branch name without the `airesearch-worktree-` or `airesearch-` prefix, so `airesearch-entrance-e2e` gets `../roadmap-worktree-entrance-e2e`.
- If the branch is already checked out in another worktree, such as under `.claude/worktrees/`, stop and report where. Git won't check out one branch in two worktrees, and moving that folder would break any session running in it, so the user decides.
- Keep the existing branch name; don't rename a branch the user already has.

### 2. Create the branch and worktree

```bash
git worktree add ../roadmap-worktree-<name> -b airesearch-worktree-<name> airesearch
../roadmap-worktree-<name>/skills/link-skills.sh
```

For an existing branch, leave out `-b`: `git worktree add ../roadmap-worktree-<name> <branch>`.

The link script creates the `.claude/skills/` symlinks inside the new worktree. `.claude/` is gitignored, so a fresh worktree has no skill links, and without them the new session can't see the project skills.

### 3. Write the brief

Write `../roadmap-worktree-<name>/.claude/brief.md`. `.claude/` is gitignored, so the brief stays out of commits. It contains:

- the user's request, verbatim
- the branch, the base and the absolute worktree path
- any context from this conversation the new session needs, such as decisions made, constraints or related work
- an instruction to run `bun install` first

When the request doesn't say what to do (say, "run that branch in a worktree"), tell the new session to review the branch state, summarize what is done and what remains, and wait for instructions.

### 4. Open the agterm session

```bash
wt="$(cd .. && pwd)/roadmap-worktree-<name>"
agtermctl session new --socket "$AGTERM_SOCKET" --after "$AGTERM_SESSION_ID" --no-select \
  --cwd "$wt" --name <name> \
  --command "zsh -ic 'claude \"\$(cat .claude/brief.md)\"; exec zsh -l'"
```

- `zsh -ic` loads `.zshrc`, whose `claude` function ties the Claude session to the agterm session so it resumes after a restart.
- `exec zsh -l` keeps the session open after Claude exits.
- `--after "$AGTERM_SESSION_ID" --no-select` places the session next to the current one without switching away from it.

### 5. Verify and report

Check that the new session's `foreground` is `claude`:

```bash
agtermctl tree --json --socket "$AGTERM_SOCKET"
```

Look up the session by the id that `session new` printed. Then tell the user the session name, branch and worktree path.

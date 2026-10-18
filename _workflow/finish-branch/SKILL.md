---
name: finish-branch
description: Finish a work branch - check that the plans and specs it added under docs/superpowers were implemented, turn whatever wasn't into docs/backlog items, archive the branch as completed/<branch-name>, remove the finished plans and specs, squash-merge it into its target base as one commit, delete the branch, and remove its worktree and folder on disk. Use whenever the user says to finish, close, wrap up, land or merge back a branch or worktree ("finish airesearch-worktree-foo", "merge this back to airesearch", "we're done with this branch, clean it up", "squash it in and remove the worktree"), even if they don't name the skill.
---

# Finish branch

Lands a finished branch as a single commit on its target and cleans up after it. Nothing is lost on the way:

- Work a plan or spec promised but the branch didn't deliver becomes a backlog item, so it isn't forgotten when the plan is deleted.
- The original commits, plans and specs included, stay reachable under `completed/<branch-name>`.

## Inputs

- **Branch**: the one the user names. If none, use the branch checked out in the current directory, unless that is the target itself; then ask.
- **Target**: the branch to squash into. If the user didn't name it, ask. Suggest the likely base in the question (the base named in the project's CLAUDE.md, a brief in `<worktree>/.claude/brief.md`, or `git merge-base` candidates), but don't assume it: landing on the wrong base is annoying to undo.

## Preflight

Check everything before changing anything, so a problem stops the run with nothing half done. Work with `git -C <path>` and absolute paths throughout: the current session may live inside the worktree that gets removed at the end.

1. Find where each branch is checked out: `git worktree list --porcelain`.
   - The branch must be checked out somewhere, because steps 1-4 commit on it. If it isn't, ask whether to add a worktree for it.
   - The branch's worktree (if any) is what gets removed at the end. If the branch is checked out in the main repo root, there is no worktree to remove; the root must switch to another branch before the branch can be deleted, so ask the user what to switch to.
   - The target must be checked out somewhere to commit on it. If it isn't checked out anywhere, ask whether to check it out in the main repo root.
2. The branch must have no uncommitted changes to tracked files (`git -C <branch-wt> status --porcelain --untracked-files=no`). If it does, stop and ask: commit them, or leave them out?
3. The target's checkout must have no staged or modified tracked files, otherwise the squash would mix them into the commit. Untracked files there are fine.
4. `completed/<branch-name>` must not already exist. If it does, ask (overwrite, or pick another name).
5. Show what will land: `git log --oneline <target>..<branch>` and `git diff --stat <target>...<branch>`. If the log is empty there is nothing to merge; say so and ask whether to just archive and clean up.

## Steps

### 1. Find the finished plans and specs

The finished plans and specs are the ones this branch added or changed:

```bash
git -C <branch-wt> diff --name-status <target>...<branch> -- docs/superpowers/plans docs/superpowers/specs
```

Only these count. Plans and specs that were already on the target and that the branch didn't touch belong to other work; leave them alone. If the list is empty, skip to step 4.

### 2. Verify they were implemented

For each finished plan and spec, go through what it promises (tasks, steps, requirements, acceptance criteria) and check each item against the branch's code, tests and docs. A ticked checkbox isn't proof: confirm the code or test exists. A plan that names a file, function or test should find it in the branch.

For more than a couple of documents, check each one in a fresh subagent, so one long document doesn't crowd out the next. Give it the document path, the worktree path, the target and the instruction to report each item as done, partly done or not done, with evidence (file and line, commit, test name).

Collect the items that are partly done or not done. For each, work out why it wasn't done: deferred on purpose, blocked, out of scope, dropped as unnecessary, or simply not reached. Look in the commits, the brief (`<branch-wt>/.claude/brief.md`), the plan's own notes and this session. If the reason can't be found, ask the user rather than guessing.

Show the user the list: what was done, what wasn't, and why. Items the user says were dropped on purpose and need no follow-up don't become backlog items, but name them in the final report.

### 3. Create backlog items for what wasn't done

Use the `backlog` skill to create one item in `docs/backlog/` per gap, or one per group of closely related gaps. If the `backlog` skill isn't available, stop and tell the user rather than inventing a format.

Each item has to stand on its own, because the plan it came from is about to be deleted. Someone picking it up months later should not need this session or the deleted plan. Include:

- what is missing, in enough detail to implement it
- the original plan or spec it came from (path), and `completed/<branch-name>` as the place to find it after deletion
- what the branch already did that this builds on: files, functions, tests
- what was learned during the work: findings, constraints, pitfalls, decisions
- why it wasn't done on this branch

Commit the backlog items on the branch, in its worktree.

### 4. Archive the branch

```bash
git branch completed/<branch-name> <branch>
```

This keeps the full pre-squash history reachable, including the plans and specs that the next step deletes and the backlog items from step 3. A full rename (`git branch -m`) fails while a worktree has the branch checked out, so copy the ref now and delete the original at the end.

### 5. Remove the finished plans and specs

Delete the finished plans and specs from step 1 in the branch's worktree and commit that on the branch. If the branch only changed a plan or spec that was already on the target before it started, ask before deleting it: it may still belong to other work.

This commit lands after the archive, so `completed/<branch-name>` still has the documents and the target doesn't get them.

### 6. Squash-merge into the target

```bash
git -C <target-wt> merge --squash <branch>
```

On conflicts, stop. Show the conflicted files and ask how to proceed (resolve here, or `git -C <target-wt> merge --abort` and rebase the branch first). Don't resolve conflicts on your own.

Then commit once. Write the message from the branch's commits and diff, in the repo's style (check `git log` on the target: prefix, tense, language). If the user gave a message, use theirs. Add any commit attribution lines the session requires.

### 7. Remove the worktree (if the branch has one)

```bash
git -C <main-repo> worktree remove <branch-wt>
```

Git refuses when the worktree has untracked files (ignored ones like `node_modules` or `.claude/` are fine). If it refuses, list those files and ask before using `--force`: they are not in any commit and will be gone.

Afterwards make sure the folder is really gone (`ls <branch-wt>`) and run `git worktree prune`. If a terminal or agent session still runs in that folder, tell the user it is now orphaned.

Never remove the main repo root.

### 8. Delete the branch

```bash
git branch -D <branch>
```

`-D` is needed because a squash merge doesn't make the branch an ancestor of the target. That's safe here: `completed/<branch-name>` holds everything except the deletion commit from step 5.

## Report

Finish with a short summary:

- the plans and specs checked, and how many of their items were done
- the backlog items created (paths), and items dropped on purpose with no backlog item
- `completed/<branch-name>` and the commit it points to
- the plans and specs removed
- the squash commit (hash + subject) and the target it landed on
- the deleted branch, and the removed worktree path
- anything skipped or still pending, such as the target now being ahead of its remote

Don't push the target or the archive branch unless the user asks.

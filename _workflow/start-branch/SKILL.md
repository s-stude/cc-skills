---
name: start-branch
description: Start new work in its own branch and sibling worktree, branched from whatever is checked out where the skill runs - name the branch <base>-worktree-<name>, add the worktree at ../<project>-worktree-<name>, record the base in git config for finish-branch, write a brief, and open a new Claude session there in agterm. Use whenever the user asks to start, open or spin up a branch or worktree for some work, to "do this in a worktree", or to run an existing branch in a separate worktree, even if they don't name the skill. Also use it for any development work when the project's CLAUDE.md says work happens in worktrees. The current session hands the work off instead of doing it itself.
---

# Start branch

Each piece of work gets its own branch, its own worktree folder next to the project, and its own Claude session. Parallel work stays isolated, the checkout you started from stays as it was, and each session can resume after a restart. When the work is done, the `finish-branch` skill lands it back on the branch it came from.

The skill works in any git project. Everything it names comes from where it runs:

- **Base**: the branch checked out in the current directory (`git branch --show-current`), unless the user names another one. That can be `main`, a long-lived integration branch, or another worktree's branch.
- **Project**: the folder name of the repository's main checkout, even when the skill runs inside a linked worktree. New worktrees always go next to the main checkout, so names don't grow with each level.

```bash
base="$(git branch --show-current)"
main_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
project="$(basename "$main_root")"
parent="$(dirname "$main_root")"
```

If `base` is empty (detached HEAD), ask which branch to start from.

The calculation above assumes the usual layout, a main checkout with a `.git` folder in it. Check it before creating anything: the repository is not bare (`git rev-parse --is-bare-repository` prints `false`), the common dir is named `.git`, and `git -C "$main_root" rev-parse --path-format=absolute --git-common-dir` gives the same common dir back. If any check fails (a bare repository, `git init --separate-git-dir`, a submodule), ask the user for the project name and the folder the worktrees should go in.

Questions, explanations, reviews and git housekeeping stay in the current session. So does work the user explicitly asks to do here.

## Naming and placement

Pick a short kebab-case `<name>` that describes the work, such as `usecases-split` or `login-e2e`.

| What | Pattern | Example (project `shop`, base `main`) |
| --- | --- | --- |
| Branch | `<base>-worktree-<name>` | `main-worktree-login-e2e` |
| Worktree folder | `<parent>/<project>-worktree-<name>`, a sibling of the main checkout | `~/code/shop-worktree-login-e2e` |
| agterm session | `<name>` | `login-e2e` |

The branch name shows where the work came from, so a branch started from another worktree's branch reads as `main-worktree-checkout-worktree-retry`. A base with slashes (`release/2.1`) stays as it is in the branch name (`release/2.1-worktree-<name>`); the folder uses only the project name.

If the project's CLAUDE.md or AGENTS.md sets its own naming or location for worktrees, follow that instead.

## Steps

### 1. Check before creating anything

Run all the checks first and create nothing until every one passes. A half-failed `git worktree add` is messy: when the folder already exists, git refuses the worktree but still creates the branch, leaving a stray branch behind.

```bash
branch="$base-worktree-<name>"
wt="$parent/$project-worktree-<name>"
git branch --list "$branch"                 # local branch
git branch -r --list "*/$branch"            # branch on a remote
test -e "$wt" && echo exists                # folder on disk
git worktree list --porcelain               # worktree registered at that path, even if its folder is gone
git status --porcelain --untracked-files=no # uncommitted changes in the current checkout
```

If the branch exists (locally or on a remote), or the folder exists, or a worktree is registered at that path, **stop and report**. Don't reuse, move, rename, prune, force or delete anything. The user decides whether to reuse the branch or the folder, or to pick another name. The report says:

- which check failed: branch (local or remote), folder, or registered worktree
- for a branch: its last commit (`git log -1 --oneline <branch>`), how far ahead of the base it is, and where it is checked out (`git worktree list`)
- for a folder: whether it is a worktree and which branch it is on, or whether it is an ordinary folder
- for a registered worktree whose folder is gone: that `git worktree prune` would clear it

Then wait for the user's answer and continue with what they choose.

Uncommitted changes in the current checkout don't block anything, but they won't be in the new worktree, which starts from the base's last commit. Mention them so the user can commit them first if the new work needs them.

**Running an existing branch.** When the user explicitly asks to run a branch that already exists, that request is their decision to reuse the branch, so the branch check doesn't stop you. Still run the folder and worktree checks:

- Name the folder after the branch: `<name>` is the part after the last `-worktree-`, or else the branch name with `/` replaced by `-`. So `main-worktree-login-e2e` gets `<project>-worktree-login-e2e` and `feature/login` gets `<project>-worktree-feature-login`.
- Work out its base: `git config --get branch.<branch>.base`, else the oldest reflog entry (`git reflog show --format=%gs <branch> | tail -1` reads `branch: Created from <base>`), else ask. Take the reflog's answer only when it names an existing local branch other than this one: `HEAD`, a commit hash, a missing branch or an entry that isn't a creation tells you nothing, so ask. Record the base as in step 2 once known.
- If the branch is already checked out in another worktree, stop and report where. Git won't check out one branch in two worktrees, and moving that folder would break any session running in it, so the user decides.
- Keep the existing branch name; don't rename a branch the user already has.

### 2. Create the branch and worktree, and record the base

```bash
git worktree add "$wt" -b "$branch" "$base"
git config "branch.$branch.base" "$base"
```

For an existing branch, leave out `-b`: `git worktree add "$wt" <branch>`.

`branch.<branch>.base` is how `finish-branch` knows where to land the work. Git keeps it with the branch: renaming the branch moves it and deleting the branch removes it.

Then prepare the worktree the way the project needs. A fresh worktree has only tracked files, so anything gitignored is missing: dependencies, `.env` files, generated code, project-local skill links under `.claude/skills/`. Look in the project's CLAUDE.md, AGENTS.md or README for setup steps and for scripts that do it. Run the cheap, local ones (linking, copying an example env file). Leave slow installs to the new session's brief.

### 3. Write the brief

Write `$wt/.handoffs/brief-000.md`: it starts session 000 of the worktree's handoff chain (`.handoffs/brief-NNN.md` starts session NNN, whose peer conversation is the folder `.peer-chats/chat-NNN/`; see the `handoff-to-new-session` and `peer-chat` skills). A new worktree starts with both folders empty, so it never inherits another effort's briefs. Keep both out of git through the local exclude file (never `.gitignore`):

```bash
mkdir -p "$wt/.handoffs"
exclude="$(git -C "$wt" rev-parse --git-path info/exclude)"; [[ "$exclude" = /* ]] || exclude="$wt/$exclude"
mkdir -p "$(dirname "$exclude")"
for dir in .handoffs .peer-chats; do git -C "$wt" check-ignore -q "$dir/x" || echo "$dir/" >> "$exclude"; done
```

The brief contains:

- the user's request, verbatim
- the branch, the base and the absolute worktree path
- any context from this conversation the new session needs, such as decisions made, constraints or related work
- the setup still to do before working (installing dependencies, building), with the commands from the project's docs
- that `finish-branch` lands the branch on its base when the work is done

When the request doesn't say what to do (say, "run that branch in a worktree"), tell the new session to review the branch state, summarize what is done and what remains, and wait for instructions.

### 4. Open the agterm session

Inside agterm (`AGTERM_SOCKET` and `AGTERM_SESSION_ID` are set):

```bash
agtermctl session new --socket "$AGTERM_SOCKET" --after "$AGTERM_SESSION_ID" --no-select \
  --cwd "$wt" --name <name> \
  --command "zsh -ic 'export HANDOFF_SEQ=000; claude \"\$(cat .handoffs/brief-000.md)\"; exec zsh -l'"
```

- `HANDOFF_SEQ=000` makes the peer-chat script name this session's conversation folder `.peer-chats/chat-000/`.
- `zsh -ic` loads `.zshrc`, so the user's own `claude` function or alias applies (for example one that ties Claude to the agterm session so it resumes after a restart). Use the user's login shell if it isn't zsh.
- `exec zsh -l` keeps the session open after Claude exits.
- `--after "$AGTERM_SESSION_ID" --no-select` places the session next to the current one without switching away from it.

Outside agterm, don't open anything. Give the user the command to start it themselves:

```bash
cd "<wt>" && HANDOFF_SEQ=000 claude "$(cat .handoffs/brief-000.md)"
```

### 5. Verify and report

In agterm, check that the new session's `foreground` is `claude`:

```bash
agtermctl tree --json --socket "$AGTERM_SOCKET"
```

Look up the session by the id that `session new` printed. Then tell the user the session name, the branch, its base and the worktree path.

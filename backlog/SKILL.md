---
name: backlog
description: File, dedupe, update and close items in docs/backlog/ - the repo's git-only record of work that is real but not being done now (a pre-existing defect, silent drift, a fix not worth its blast radius, an idea worth keeping). Use whenever a review, plan check, debugging session or finish-branch run turns up something deferred, whenever the user says "add to backlog", "note this for later", "park this", "we won't fix this now", "file this", or asks what's in the backlog, even if they don't name the skill.
---

# Backlog

`docs/backlog/` at the repo root holds work that is real but not being done now: a defect a change did not introduce, drift with no user-visible symptom, a fix whose blast radius exceeded its value, an idea worth keeping. One file per item.

It is git only. There is no tracker and no status field: an item exists while its file exists, and `git rm` closes it. History is `git log -- docs/backlog/`.

## Item format

`docs/backlog/<slug>.md`. The slug names the defect, not the file it lives in (`export-drops-empty-rows.md`, not `exporter.md`), so it can be cited from a commit and dedupe starts with a filename check.

```markdown
---
worth: <yes | no | later>
where: <path/to/file>:<line>
added: YYYY-MM-DD
---
# <what is wrong, in one line>

<What happens and under which conditions, as the user or caller would notice it. Where it surfaced: a
review, a test run, a debugging session. Why it was deferred rather than fixed on the spot.>
```

Three frontmatter fields, written once and rewritten only as **Appending** below allows:

- **`worth: yes | no | later`** is the triage call, and the field the list is ordered by.
  - **`yes`**: the value is agreed and it should be fixed. It says nothing about schedule: an item blocked on an upstream release is still `yes` if nobody disputes it is worth doing.
  - **`later`**: the value decision itself is unresolved, not the work. The body must name the unknown or the condition that would settle it; without that it is a `yes` or a `no` in disguise.
  - **`no`**: a decision not to fix, kept so the same finding is not rediscovered and re-argued by the next review that touches the file. Keep a `no` only while that rationale still earns its place; once it doesn't, delete the file rather than carrying it.
- **`where: path:line`**: omit it when the item is not anchored to one place. The path narrows the dedupe search alongside the slug; the line is a navigation hint that moves. Compare paths only when both items have `where`; two items missing it are not thereby the same item.
- **`added: YYYY-MM-DD`** is never updated, so it reads as age. A year-old item is itself information. Zero-pad it so the values sort lexically.

The H1 is the title. The body below it has no required sections: repro, what was tried, the review that surfaced it, links, a snippet, in whatever shape suits. A two-line item stays two lines; a gnarly one gets a page. Two kinds of item owe one sentence each, which a two-line body can carry:

- a `later` names the unknown that would settle its value decision
- a `no` records why the fix was rejected, without which it can't do the anti-rediscovery job it is kept for

## Appending

When a run produces deferred items, offer to append them; never write silently.

### 1. Check the branch first

Never add a backlog item to an unrelated work branch. Repo-wide notes dropped into someone else's in-progress branch get swept into that branch's diff or vanish with it. Check the branch before creating the directory or writing any file.

1. **Find the default branch.** Read `git symbolic-ref refs/remotes/origin/HEAD` and strip the `refs/remotes/origin/` prefix. If that command fails or returns nothing (it exits non-zero when the ref is not symbolic, which is the usual signal), fall back to two ordered passes with `git rev-parse --verify`, remote first and complete before local:
   1. `refs/remotes/origin/master`, then `refs/remotes/origin/main`, then `refs/remotes/origin/trunk`
   2. only if none of those resolves: `refs/heads/master`, then `refs/heads/main`, then `refs/heads/trunk`

   Don't interleave the two passes per candidate. A repo migrated to `main` can keep a stale local `master`, and checking local `master` before remote `main` picks the dead branch as the default. Probe the full ref paths, so a tag of the same name can't answer for a branch.

   **Project override:** if the project's CLAUDE.md names a different branch as the base for work (this repo's names `airesearch` instead of `main`), that branch is the default for this check, whatever the detection returns.
2. **Compare it with `git branch --show-current`.** If no default branch was found at all, say so and take the "anywhere else" case: there is nothing to compare against, so the answer must come from the user rather than a guess.
   - **On the default branch**: write in place.
   - **Anywhere else**: report the current branch by name, or `detached HEAD at <sha>` when the command returns nothing, and ask whether to write in this checkout anyway. On yes, write here. On no, change nothing: don't create a branch, a worktree or a temp checkout, don't switch the current checkout, and don't pick a destination the user didn't name.

**Called from `finish-branch`:** the items record gaps in the branch being finished, so that branch is the related branch, not an unrelated one. The user's request to finish it is the answer to "write here?": write in that branch's worktree without asking again. `finish-branch` commits the items on the branch itself and squashes them into the target; don't offer to push that work branch.

### 2. Dedupe before writing

The `where` path and the slug find the candidates; what settles it is the defect each one claims. A shared path is not a duplicate on its own, since one file holds several unrelated defects, and the trailing line moves with any edit above it.

A pre-existing defect surfaces in every review that touches its file, so the same item arrives repeatedly. If it is already there, say so and leave it alone. If the new sighting sharpens the description or changes the `worth` call, edit that file in place rather than adding a second one.

### 3. Write

Create `docs/backlog/` if it doesn't exist: after the branch check, never before it. Write one file per item in the format above. `added` is today's date for new items and stays as it was for edited ones.

### 4. Offer commit and push

Once the files are written, read `git diff --cached --name-only` before offering anything. Nothing has been staged yet at that point, so anything it lists is pre-existing, including another backlog file from an earlier run. If it lists anything at all, don't commit: report what is staged and let the user resolve it, because a plain `git commit` would sweep it in alongside the item.

With an empty index, offer the next step with **AskUserQuestion**. Stage the exact paths this run created or edited, not the directory: an item bundled with the run's other changes breaks the rule below. Never commit without that answer. Offer commit and push together: a backlog item is notes with no code in it, and unpushed it stays invisible from every other machine, so the push is part of filing rather than an upsell.

## Closing an item

`git rm docs/backlog/<slug>.md`, committed with the fix that resolves it (cite the slug in the commit message), or on its own when the item is dropped. The same rules apply: don't do it without being asked, and stage only that path.

## Rules

- **Never post a backlog item to a PR, MR or issue thread** unless the user explicitly asks. These are the maintainer's cleanup notes; surfacing them on a contributor's change reads as scope pressure.
- **Never auto-commit** an item file, and never commit it alongside unrelated work.
- **Don't fix an item without being asked.** Reading the backlog is not permission to work it.
- **Prefer deleting to demoting** for an item nobody will ever do and whose reasoning nobody needs: say so and offer to drop it. This doesn't reach a `no` that is still doing its job of stopping a rediscovery; that one stays.

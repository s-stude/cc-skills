# Plan template

Copy into the project's plan folder and fill in. Keep it short enough that the peer can review it in
one read; detail belongs in the tasks, not in prose.

```markdown
# Implementation plan: <title>

Status: draft, awaiting peer review. Updated: <date>.

## Goal

<what the user asked for, in one paragraph; quote their words where they are precise>

## Keep

- <components, APIs, behaviour that must survive unchanged>

## Remove / Add

- <what goes away or is new, concrete: files, config keys, endpoints, scripts, docs>

## Design

<only the decisions that are not obvious from the lists above: new interfaces, data or API shape
changes, migration of existing user state, error codes, security constraints>

## Tasks

One task = one commit; each commit keeps the app usable and the full suite green, and is reviewed by
the peer before the next one starts.

- [ ] **T1 — <name>.** <what changes, which files, which tests prove it>
- [ ] **T2 — …**

## Verification

- <full check commands>
- <stale-reference grep, scoped to active files, with the allowed exceptions named>
- <live or costly checks: only with the user's approval>

## Decisions

<filled during the run: question, decision, reason, who decided (user / peer / default)>

## Open questions for review

1. <question> — recommended: <option>, because <reason>.
```

Before sending it for review, walk the task list once more: for each task, list what it removes or
renames and grep for the remaining callers. A caller that survives into a later task means the two
changes belong in the same commit or the order is wrong.

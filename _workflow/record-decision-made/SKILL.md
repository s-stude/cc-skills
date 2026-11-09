---
name: record-decision-made
description: Record a decision as an architecture decision record (ADR) in docs/adr/NNN-decision-slug.md, with Date, Context, Decision, Who decided, Consequences and How to reverse. Use it whenever a decision with real consequences gets made, especially when YOU, the AI agent, make it on the user's behalf. That covers picking a library, framework, data model, storage, protocol or default; resolving an open question in a plan or spec; choosing between options a reviewer offered; cutting or deferring scope; accepting a trade-off; or working around a missing requirement while the user is away. Also use it when the user decides something ("let's go with X", "park it", "keep the defaults", "no deploy, local only"), confirms or overrules an earlier agent decision, or when a new decision replaces an old one. Use it even if nobody says "ADR" and even in the middle of other work: an unrecorded agent decision is the one the user can't find or reverse later.
---

# Record a decision

An ADR is a one-page note that answers, months later: what was decided, why, who decided, what it
costs, and how to undo it. Its main job here is to make **decisions an AI agent made on its own**
visible and reversible. The user can't review a choice they never heard about. A short file in the
repo turns "the agent quietly picked X" into "the agent picked X, here is why, and here is the
one-sentence way back".

## When a decision deserves an ADR

Write one when someone later could reasonably ask "why is it like this?" and the answer isn't obvious
from the code:

- choosing between real alternatives (library, queue, database, auth method, file layout, API shape);
- a default with consequences (retention period, timeouts, which data source wins, sampling policy);
- answering an open question from a plan, spec or review;
- scope: deferring, cutting or parking something, or accepting a known limitation;
- the user stating a decision in chat that the code must follow;
- the user confirming or overruling an earlier decision;
- a decision that replaces an earlier one.

Skip it for choices the codebase already dictates (existing conventions, naming, formatting) and for
trivial, easily changed details. A test: if reversing it later would surprise someone or cost more
than a few minutes, record it.

Record it **when the decision is made**, as part of the same piece of work and ideally the same commit
as the change it governs. ADRs written in bulk afterwards lose the context that made them useful.

## Where and how to name it

- Directory: `docs/adr/` at the repository root (create it if missing).
- File: `docs/adr/NNN-decision-slug.md`: a three-digit number, one above the highest existing one,
  then a short kebab-case slug of the decision, e.g. `014-raw-retention-forever.md`.
- `scripts/next-adr.sh <slug>` (in this skill's directory) prints the next free path:
  ```bash
  bash <this-skill-dir>/scripts/next-adr.sh raw-retention-forever
  # docs/adr/014-raw-retention-forever.md
  ```
- If the project already has ADRs in another place or style (for example `docs/decisions/`, or a
  template in `docs/adr/000-template.md`), follow the project's location and template. Still make sure
  every required field below is present.

## Required content

Use this template. Keep it short: most ADRs fit in 15–40 lines.

```markdown
# ADR-NNN: <decision in a few words>

- **Date:** YYYY-MM-DD
- **Status:** accepted | proposed | superseded by ADR-NNN
- **Who decided:** user | agent (awaiting user confirmation) | agent, confirmed by user YYYY-MM-DD
- **Related:** <plan item, issue, spec section, earlier ADR — or "none">

## Context

The problem and the forces behind it: what needed deciding, what constraints applied, what was known.
Include evidence and where it came from (code, docs, a measurement, the user's words).

## Decision

The choice, stated precisely enough that code and tests can be checked against it.
Mention the main alternatives that were rejected and why, in a sentence each.

## Consequences

What follows: what becomes easier, what becomes harder, follow-up work, risks, costs.

## How to reverse

What the user would say or do to undo it, and what would have to change in code, data or settings.
Aim for one or two sentences the user can act on.
```

Field guidance:
- **Date** is the day the decision was made, in `YYYY-MM-DD` format.
- **Who decided** is the field that matters most. Say "agent" plainly when you chose. Don't dress an
  agent default up as a user decision, and don't call something "agreed" because a reviewer (human or
  AI) approved the code. Only the user's own words make it a user decision; quote them in Context when
  you have them.
- **How to reverse** is never "not applicable". If something is truly hard to undo (a data migration,
  a published API), say so and explain the cost; that is exactly what the user needs to know.

## Keeping the record honest over time

- **The user confirms an agent decision:** edit the existing ADR in place. Set "Who decided" to
  `agent, confirmed by user YYYY-MM-DD`, and add a line to Context with what they said. Don't create a
  new ADR for a plain confirmation.
- **The user overrules it, or a new decision replaces an old one:** write a new ADR. Set the old one's
  Status to `superseded by ADR-NNN`, and say in the new one which ADR it replaces. Don't rewrite history
  in the old file; the trail of what changed and why is the point.
- **Index:** if `docs/adr/README.md` exists, add or update its row (number, one-line decision, status,
  who decided). If it doesn't exist and there are now three or more ADRs, create it with a small table.
  It's the page a person scans first.

## Tell the user

After writing or updating an ADR, mention it in your reply in one line: the file path, the decision,
and, for agent decisions, that it awaits their confirmation and how to reverse it. The file exists so
the user can find it later; the one-line mention is so they notice it now.

## Example

The user is away; the plan says "raw retention: TBD"; the agent picks "keep forever".

`docs/adr/005-raw-retention.md`:

```markdown
# ADR-005: Keep raw provider responses forever by default

- **Date:** 2026-11-07
- **Status:** accepted
- **Who decided:** agent (awaiting user confirmation)
- **Related:** plan open question 4 (D-5)

## Context

The plan leaves raw retention open (D-5). Raw responses make replay possible after a parser fix;
deleting them cannot be undone. Volume is small: about 2 MB a month per site, measured in Task 22.

## Decision

Setting `RAW_RETENTION_DAYS`; unset means keep forever. When it is set, a daily job deletes older raw
responses. Rejected: a 90-day default, because it silently limits replay before anyone has decided.

## Consequences

The database grows by about 25 MB a year per site. Replay works for all history. A later retention
choice is one setting.

## How to reverse

Set `RAW_RETENTION_DAYS=<days>` in `.env`; the next daily run deletes anything older. Nothing else
changes.
```

Reply line: "Recorded `docs/adr/005-raw-retention.md`: raw responses are kept forever by default (agent
decision, awaiting your confirmation; set `RAW_RETENTION_DAYS` to change it)."

# What to look for, and how to measure it

Questions to answer per transcript, each with how to get the number. Not every question applies to every agent:
skip the ones that don't, and say so in one line.

## Contents

1. Task and outcome
2. Cost and size
3. Coverage and honesty
4. Precision and value
5. Process waste
6. Convergence across rounds
7. Method
8. Brief quality
9. Rule compliance
10. Patterns seen before

## 1. Task and outcome

- **What was asked:** `prompt-1.md` (the brief), and each later `prompt-N.md` with the trigger `coordinator` or
  `user`.
- **What was delivered:** `report-N.md`, or `last-text-N.md` when there was no handback.
- **Did the delivery match the ask?** List anything asked but not done, and anything done but not asked.
- **Dates and duration:** from `stats.json` › `rounds` and `totals.wall_s`. Wall time includes idle gaps;
  per-round `wall_s` is closer to working time.

## 2. Cost and size

- **Per round:** calls, max context, cache read, cache write and output, from `stats.json` › `rounds`.
- **Totals and their ratio:** output tokens against cache-read tokens. A ratio under about 1:300 means the agent
  mostly re-read its own context.
- **Pricing [docs]:** cache read is about 0.1× the input price, cache write about 1.25×, so 1M written is worth
  about 12.5M read.
- **Cache rewrites:** list each with its gap and whether the gap passed the cache lifetime. Price them.
- **Size per cause:** `entry_mb`, `tool_result_mb` and `images`.
- **Cost per image:** context growth divided by images read, over a round with few other reads. An image's long
  side over 1568 px is downscaled by the API [docs], so those pixels are paid for but never seen. The sizes are in
  `image_sizes`.

## 3. Coverage and honesty

- **Items asked vs items opened:** count opened items from `timeline.tsv` (the Read calls), never from the
  agent's own claim. Compare with the list the brief gave, or the folder's contents.
- **Claims to compare with the Read calls:** "all", "every", "N pages checked", "regression pass clean". Report
  each mismatch with both numbers.
- **Samples and proxies:** contact sheets, crops, "quick pass", inferring the rest "from the same helper". Was
  this disclosed? Did it lead to findings about unopened items?
- **Verdicts from memory:** a claim about a file the agent did not (re-)read in that round. Example: the test file
  changed, but the agent never opened it again.

## 4. Precision and value

- **How the findings were received:** grep the coordinator's transcript in the agent's time window:

  ```bash
  python3 -I scripts/cc_jsonl.py grep <session>.jsonl "<finding keyword>|fix|wrong|reject|cosmetic" --since <ts> --until <ts> --roles assistant
  ```

  Sort each finding into accepted, disputed, ruled out by decision, or ignored. Give counts.
- **Was it acted on?** Check `git log --since/--until`, the files named in the findings, and the project's issue or
  backlog records. Spot-check a few; this is not a full audit.
- **Most valuable findings:** name the ones the project's own checks, tests or reviewers missed.
- **Ranked too low:** a "minor" finding that turned out to hide a real defect.
- **Silent drops:** findings left open and recorded nowhere.

## 5. Process waste

- **Context carried for nothing:** an agent reused for a new round keeps everything it read before. Report the max
  context per round, and the cost of later rounds against round 1.
- **Small batches:** `reads_per_call`. Many calls with 1–4 Reads, at a large context, re-send that context each
  time.
- **Re-reads:** `reads_repeated`, and `sed` of a range followed by a Read of the same range.
- **Errors and stops:** `anomalies`. Note what each cost: lost wall time, the re-sent context, a resume brief that
  was wrong about the progress.
- **Rewritten helpers:** the same throwaway script written in every round or by every agent. That is a candidate
  tool to ship.
- **Idle gaps:** spans between rounds, and what filled them (from the coordinator's transcript).

## 6. Convergence across rounds

- **Findings per round,** and whether they reached zero.
- **Recurring findings (3+ rounds):** why each fix didn't stick. Usually the fix moved the defect instead of
  removing it:
  - a fix by text instead of by identity;
  - one text built in two places;
  - a sibling file missed;
  - tuning by eye.
- **Regressions caused by a fix,** and whether they were caught on purpose or by chance.
- **Closing check:** was the final committed state ever reviewed? Compare the time of the last review round with
  the commits after it. Did anyone say "passed" for something not reviewed?

## 7. Method

- **What its Bash calls did,** from `timeline.tsv`: crops, report files, HTML-to-text, hashes, diffs, greps.
- **Which methods made findings reliable,** and which made them less reliable (partial crops, unlabelled sheets).
- **Missing tools** it worked around: a library not installed, and which fallback it used.

## 8. Brief quality

- **What the agent had to work out alone:** files, conventions, earlier decisions, harness limits.
- **What it lacked:**
  - the earlier findings and their status;
  - rulings, which is why rejected findings keep coming back;
  - what changed since the last round;
  - known limits;
  - that a parallel process was writing the same files.
- **Wording that invited shortcuts:** "quick look", "only new findings", "same as before".
- **Wording that misled:** "while you were working" sent to a finished agent; a resume brief that was wrong about
  the progress.

## 9. Rule compliance

- Files it was told not to open: check the paths in `timeline.tsv` against the brief's "do not" list.
- Edits or commits when read-only. Look for `Edit`, `Write`, `git commit` and `rm` in `timeline.tsv`.
- Actions outside its scope: messages, pushes, deletes.

## 10. Patterns seen before

These came up across many agents in one project. Check for each; confirm, contradict or add a number:

- **Reusing one agent across rounds** roughly doubles each later round. Coverage drops past about 560k context or
  100+ items per round.
- **An idle gap longer than the cache lifetime,** or a stream error, rewrites the whole context into the cache.
- **Self-reported coverage** is wrong often enough that it must be counted.
- **Verdicts from memory** after the source changed.
- **Local fixes** that move a defect instead of removing it.
- **No closing review** of the final state; leftovers recorded nowhere.
- **Agents rediscover the same undocumented files and tools,** and rewrite the same helper scripts.
- **A parallel process** (a mutation run, a build) writes the files a reviewer is reading.
- **Every image is stored three times** in the transcript.

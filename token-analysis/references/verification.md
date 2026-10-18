# Verification checklist

Run through this before handing the report over. Every item caught a real error at least once.

## Scope
- [ ] `inventory.py` output reviewed. Every transcript folder is either in scope or listed as excluded with a reason.
- [ ] The session filter is neither too narrow nor too wide. Compare `summary.json` `sessions` against the inventory. Early sessions on `main` that seeded the work are included or explicitly excluded.
- [ ] The requested start date was checked against the first event, and any mismatch was stated.
- [ ] Team or pre-existing commits are excluded. `git log --format=%an <scanned refs> --not <main refs> | sort | uniq -c` shows only the user.

## Tokens
- [ ] Dedup works. The number of unique calls is far below the `assistant` line count, and no single `message.id` appears in two sessions unless it was forked or resumed.
- [ ] Subagent output looks like a placeholder (recorded output per call ≪ 100) and the re-estimate is reported next to it.
- [ ] Transcript cost against the `cost-state` ledger. The gap is explained (side calls, subagent output, sessions without a ledger). A gap above about 20% is investigated.
- [ ] No `WARNING: no price` on stderr, or every missing model was given a price.
- [ ] Cost split by token class adds up to the total.
- [ ] Spot-check one session by hand. Sum `usage` for its unique message ids with a small `python3 -c` and compare it to its row in section 2.

## Time
- [ ] Agent busy (union) ≤ calendar span, and the sum ≥ the union.
- [ ] Human-engaged time ≤ activity blocks. Typing estimate ≪ engaged time.
- [ ] Days and hours are in the user's timezone (`--tz`).
- [ ] Long sleep/poll or e2e wall times are matched to background runs or soaks, not mistaken for idle time.

## Git
- [ ] `git_summary.json` `total` = the sum of the statuses, and `distinct` ≤ `total`.
- [ ] The net LOC of the landed ref matches `git diff --shortstat $(git merge-base <landed> <main>) <landed>` run by hand.
- [ ] Which branch is the real integration line? Check `git merge-base --is-ancestor A B` between candidate refs. A finish/squash flow may land on a branch other than the obvious one. Pass that branch in `--landed`, last.
- [ ] Dangling commits are bounded by `--since` if other people's or older work lives in the same object store.
- [ ] Separate repos (scratch clones, sibling repos) were run separately or explicitly excluded.

## Report
- [ ] Every headline number in the executive summary appears in a detailed section (no number without a source table).
- [ ] Percentages recomputed from the tables (e.g. a branch's share of cost).
- [ ] Each estimate is labeled as an estimate, with its method.
- [ ] Raw CSVs were written where the user asked (or next to the report), and they are untracked or gitignored.
- [ ] No project code was changed. `git status` shows only the report and CSVs.

#!/usr/bin/env python3
"""Commit, branch and lines-of-code analysis for one git repository. See ../SKILL.md."""
import argparse, collections, json, os, re, subprocess, sys
from datetime import datetime, timezone, timedelta

ap = argparse.ArgumentParser(description='Count commits (incl. killed ones) and LOC for an author in a repo')
ap.add_argument('--repo', default='.', help='path to the repository (any worktree of it)')
ap.add_argument('--author', help='author regex (default: git config user.name)')
ap.add_argument('--main', nargs='*', help='refs holding pre-existing/team history; commits reachable from them are excluded (default: main/master and their origin copies that exist)')
ap.add_argument('--branch-regex', default='.*', help='only refs whose short name matches are scanned and listed')
ap.add_argument('--landed', nargs='*', default=[], help='refs that count as "landed" work, in priority order (e.g. the integration branch)')
ap.add_argument('--archive-regex', default=r'(^|/)(completed|archive|done)/', help='refs matching this are archives of finished branches')
ap.add_argument('--backup-regex', default=r'backup', help='refs matching this are backups')
ap.add_argument('--since', help='YYYY-MM-DD; ignore commits authored before (useful to bound dangling commits)')
ap.add_argument('--until', help='YYYY-MM-DD; ignore commits authored after')
ap.add_argument('--areas', help='JSON file: ordered list of [path_regex, label] used to group LOC by area')
ap.add_argument('--tz', type=float, default=None, help='report timezone as hours offset from UTC (default: local)')
ap.add_argument('--section', default='6', help='section number to use in headings')
ap.add_argument('--name', default='', help='suffix for output files when analyzing several repos (git-<name>.md)')
ap.add_argument('--out', required=True)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
TZ = timezone(timedelta(hours=args.tz)) if args.tz is not None else datetime.now().astimezone().tzinfo
TZNAME = f'UTC{args.tz:+g}' if args.tz is not None else datetime.now().astimezone().strftime('%Z')
REPO = os.path.abspath(os.path.expanduser(args.repo))

def g(*a, inp=None):
    return subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True, input=inp).stdout

def short(r):
    return re.sub(r'^refs/(heads|remotes)/', '', r)

author = args.author or re.escape(g('config', 'user.name').strip())
if not author:
    sys.exit('no --author and no git user.name')
AUTH = re.compile(author)
main_refs = args.main if args.main is not None else [r for r in ('main', 'master', 'origin/main', 'origin/master') if g('rev-parse', '--verify', '-q', r).strip()]
if args.main is None and not main_refs:
    sys.exit('no --main refs found; pass --main <ref> (use --main with no refs only if the whole history is yours)')
BR = re.compile(args.branch_regex)
refs = [r for r in g('for-each-ref', '--format=%(refname)', 'refs/heads', 'refs/remotes').split() if not r.endswith('/HEAD') and BR.search(short(r))]
for r in args.landed:
    if g('rev-parse', '--verify', '-q', r).strip() == '':
        sys.exit(f'--landed ref not found: {r}')

NOT = ['--not', *main_refs] if main_refs else []
on_main = set(g('rev-list', *main_refs).split()) if main_refs else set()
from_refs = set(g('rev-list', *refs, *NOT).split()) if refs else set()
from_reflog = set(g('rev-list', '--reflog', *NOT).split())
all_reachable = set(g('rev-list', '--all').split())
unreach = set()
for line in g('fsck', '--unreachable', '--no-reflogs').splitlines():
    p = line.split()
    if len(p) == 3 and p[1] == 'commit': unreach.add(p[2])

since = datetime.fromisoformat(args.since).replace(tzinfo=TZ) if args.since else None
until = datetime.fromisoformat(args.until).replace(tzinfo=TZ) + timedelta(days=1) if args.until else None
info = {}
for h in (from_refs | (from_reflog - all_reachable) | unreach) - on_main:
    parts = g('show', '-s', '--format=%H%x00%an%x00%aI%x00%P%x00%s%x00%b', h).split('\x00')
    if len(parts) < 6 or not AUTH.search(parts[1]): continue
    ad = datetime.fromisoformat(parts[2])
    if (since and ad < since) or (until and ad >= until): continue
    info[h] = dict(h=h, author=parts[1], adate=parts[2], parents=parts[3].split(), subj=parts[4], body=parts[5])

contained = collections.defaultdict(set)
for r in refs:
    for h in g('rev-list', r, *NOT).split():
        if h in info: contained[h].add(short(r))
landed = [short(r) if r.startswith('refs/') else r for r in args.landed]
A_RX, B_RX = re.compile(args.archive_regex), re.compile(args.backup_regex)
for h, c in info.items():
    files = []
    if len(c['parents']) <= 1:
        for line in g('show', '--numstat', '--format=', '-M', h).splitlines():
            p = line.split('\t')
            if len(p) == 3:
                files.append((p[2], int(p[0]) if p[0] != '-' else 0, int(p[1]) if p[1] != '-' else 0))
    c['files'] = files
    c['add'] = sum(f[1] for f in files); c['del'] = sum(f[2] for f in files)
    c['merge'] = len(c['parents']) > 1
    pid = g('patch-id', '--stable', inp=g('show', h)).split()
    c['pid'] = pid[0] if pid else h
    rs = c['refs'] = sorted(contained[h])
    c['claude'] = bool(re.search(r'co-authored-by:.*(claude|anthropic)', c['body'], re.I))
    st = None
    for L_ in landed:
        if any(r == L_ or r.endswith('/' + L_) for r in rs):
            st = f'landed on {L_}'; break
    if st is None:
        if any(A_RX.search(r) for r in rs): st = 'archived (finished-branch archive ref)'
        elif any(not B_RX.search(r) for r in rs): st = 'on another branch: ' + ', '.join(sorted(r for r in rs if not B_RX.search(r))[:2])
        elif rs: st = 'backup ref only'
        elif h in from_reflog: st = 'killed (reflog only)'
        else: st = 'killed (dangling, unreachable)'
    c['status'] = st

AREAS = [(re.compile(rx), lab) for rx, lab in json.load(open(os.path.expanduser(args.areas)))] if args.areas else []
def area(path):
    for rx, lab in AREAS:
        if rx.search(path): return lab
    if re.search(r'(^|/)(bun\.lockb?|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|poetry\.lock|go\.sum)$', path): return 'lockfiles'
    if re.search(r'\.(test|spec)\.|(^|/)(tests?|__tests__|e2e|spec)/', path): return 'tests: ' + '/'.join(path.split('/')[:2])
    if path.endswith('.md') or path.startswith('docs/'): return 'docs: ' + '/'.join(path.split('/')[:2]) if '/' in path else 'docs: (root *.md)'
    parts = path.split('/')
    if parts[0] in ('apps', 'packages', 'services', 'libs', 'modules', 'crates') and len(parts) > 2: return '/'.join(parts[:2])
    return parts[0] if len(parts) > 1 else '(root files)'

C = sorted(info.values(), key=lambda c: c['adate'])
nm = [c for c in C if not c['merge']]
S = args.section
L = []; w = L.append
w(f'## {S}. Git\n')
w(f"Repository `{REPO.replace(os.path.expanduser('~'), '~')}`. Commits whose author matches `{author}` and that are not reachable from {', '.join('`' + r + '`' for r in main_refs) or '(nothing: whole history counted)'}"
  + (f", authored {args.since or '…'} to {args.until or '…'}" if args.since or args.until else '') + '. '
  "Sources: the scanned refs (local and remote), the reflog, and commits `git fsck --unreachable` still finds in the object store (rebased, squashed or reset-away work). "
  "Dangling commits cannot be tied to a branch, so bound them with `--since` when other work shares the repo.\n")
st = collections.Counter(c['status'] for c in C)
w('| Status | Commits |')
w('|---|---:|')
for k, v in st.most_common(): w(f'| {k} | {v} |')
w(f"| **All commits ever created** | **{len(C)}** |")
w(f"| of which merge commits | {sum(c['merge'] for c in C)} |")
w(f"| distinct changes (unique `git patch-id`, rebased copies collapsed) | {len({c['pid'] for c in nm})} |")
w(f"| commits with a Claude co-author trailer | {sum(c['claude'] for c in C)} |\n")

w(f'### {S}.1 Commits per day (author date, {TZNAME})\n')
w('| Day | Commits created | Still on a ref | Killed | Lines + | Lines − |')
w('|---|---:|---:|---:|---:|---:|')
bd = collections.defaultdict(list)
for c in C: bd[datetime.fromisoformat(c['adate']).astimezone(TZ).strftime('%Y-%m-%d %a')].append(c)
for k in sorted(bd):
    cs = bd[k]
    w(f"| {k} | {len(cs)} | {sum(1 for c in cs if not c['status'].startswith('killed'))} | {sum(1 for c in cs if c['status'].startswith('killed'))} | {sum(c['add'] for c in cs):,} | {sum(c['del'] for c in cs):,} |")
w('')

w(f'### {S}.2 Branches and refs\n')
w('Commits on each ref that match the author and are not on the main refs. One commit can sit on several refs (work branch, remote copy, backup, archive).\n')
w('| Ref | Commits | First | Last |')
w('|---|---:|---|---|')
for r in refs:
    hs = [h for h in g('rev-list', r, *NOT).split() if h in info]
    if not hs: continue
    ds = sorted(info[h]['adate'] for h in hs)
    w(f"| `{short(r)}` | {len(hs)} | {datetime.fromisoformat(ds[0]).astimezone(TZ):%m-%d %H:%M} | {datetime.fromisoformat(ds[-1]).astimezone(TZ):%m-%d %H:%M} |")
w('')
seen_names = set()
for line in g('reflog', '--all', '--format=%gs').splitlines():
    for m in re.finditer(r'moving from (\S+) to (\S+)', line): seen_names.update(m.groups())
    for m in re.finditer(r'(?:Created from|branch: Renamed \S+ to) (\S+)', line): seen_names.add(m.group(1))
live = {short(r) for r in g('for-each-ref', '--format=%(refname)', 'refs/heads').split()}
gone = sorted(b for b in seen_names if b not in live and BR.search(b) and not re.fullmatch(r'[0-9a-f]{7,40}|HEAD|(origin|[\w-]+)/.*', b))
wts = [l.split()[1] for l in g('worktree', 'list', '--porcelain').splitlines() if l.startswith('worktree ')]
w(f"* Branches seen in the reflog that no longer exist: {', '.join('`' + b + '`' for b in gone) or 'none'}.")
w(f"* Live worktrees: {', '.join('`' + p.replace(os.path.expanduser('~'), '~') + '`' for p in wts)}.\n")

w(f'### {S}.3 Lines of code\n')
nets = []
for r in landed:
    base = g('merge-base', r, *main_refs[:1]).strip() if main_refs else '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    nets.append((r, base, g('diff', '--shortstat', base, r).strip()))
    w(f"* **Net change on `{r}`** (`{base[:8]}..{r}`, base = {'merge-base with ' + main_refs[0] if main_refs else 'empty tree'}): {nets[-1][2] or 'no change'}.")
for r in refs:
    sr = short(r)
    if not landed: break
    if not A_RX.search(sr): continue
    base = g('merge-base', r, landed[-1]).strip()
    own = g('rev-list', '--count', r, '--not', base).strip()
    if own == '0': continue
    w(f"* Archive `{sr}`: {own} commits of its own after forking from `{landed[-1]}` at `{base[:8]}`; net: {g('diff', '--shortstat', base, r).strip()}.")
ga = sum(c['add'] for c in nm); gd = sum(c['del'] for c in nm)
seen = set(); ua = ud = 0
for c in nm:
    if c['pid'] in seen: continue
    seen.add(c['pid']); ua += c['add']; ud += c['del']
w(f"* **Gross churn, every commit ever created** (incl. killed and rebased copies): **+{ga:,} / −{gd:,}**.")
w(f"* Gross churn over distinct changes (patch-id deduplicated): **+{ua:,} / −{ud:,}**.\n")

if nets:
    r, base, _ = nets[-1]
    w(f'#### Net change by area (`{base[:8]}..{r}`)\n')
    w('| Area | Files | Lines + | Lines − |')
    w('|---|---:|---:|---:|')
    aa = collections.defaultdict(lambda: [0, 0, 0])
    for line in g('diff', '--numstat', '-M', base, r).splitlines():
        p = line.split('\t')
        if len(p) == 3:
            x = aa[area(p[2])]; x[0] += 1; x[1] += int(p[0]) if p[0] != '-' else 0; x[2] += int(p[1]) if p[1] != '-' else 0
    for k, v in sorted(aa.items(), key=lambda kv: -kv[1][1]): w(f'| {k} | {v[0]} | {v[1]:,} | {v[2]:,} |')
    w('')
w('#### Gross churn by area (distinct changes)\n')
w('| Area | Lines + | Lines − |')
w('|---|---:|---:|')
ab = collections.defaultdict(lambda: [0, 0]); seen = set()
for c in nm:
    if c['pid'] in seen: continue
    seen.add(c['pid'])
    for f, a, d in c['files']:
        x = ab[area(f)]; x[0] += a; x[1] += d
for k, v in sorted(ab.items(), key=lambda kv: -kv[1][0]): w(f'| {k} | {v[0]:,} | {v[1]:,} |')
w('')
w('#### Commit types (conventional-commit prefix)\n')
ty = collections.Counter((re.match(r'(\w+)(\([^)]*\))?!?:', c['subj']) or [None, 'other'])[1] for c in C)
w('| Type | Commits |')
w('|---|---:|')
for k, v in ty.most_common(): w(f'| {k} | {v} |')
w('')
w('#### Reflog activity (all refs)\n')
ra = collections.Counter()
for line in g('reflog', '--all', '--format=%gs').splitlines():
    m = re.match(r'\s*([\w -]+?)(?:\s*\(|:)', line)
    ra[(m.group(1).strip() if m else 'other')] += 1
w('| Action | Reflog entries |')
w('|---|---:|')
for k, v in ra.most_common(15): w(f'| {k} | {v} |')
w('')

A = []
A.append(f"## Appendix C. Every commit{' (' + args.name + ')' if args.name else ''}\n")
A.append(f'| # | Date ({TZNAME}) | Hash | Status | +/− | Subject |')
A.append('|---:|---|---|---|---:|---|')
for i, c in enumerate(C, 1):
    A.append(f"| {i} | {datetime.fromisoformat(c['adate']).astimezone(TZ):%m-%d %H:%M} | `{c['h'][:8]}` | {c['status']} | +{c['add']:,}/−{c['del']:,} | {c['subj'].replace('|', '/')[:90]} |")
A.append('')
SUF = '-' + args.name if args.name else ''
open(f'{args.out}/git{SUF}.md', 'w').write('\n'.join(L))
open(f'{args.out}/git{SUF}-appendix.md', 'w').write('\n'.join(A))
json.dump(dict(repo=REPO, author=author, main_refs=main_refs, total=len(C), status=st, distinct=len({c['pid'] for c in nm}),
               gross=(ga, gd), distinct_churn=(ua, ud), net={r: s for r, _, s in nets}), open(f'{args.out}/git{SUF}-summary.json', 'w'), indent=1, default=str)
print(open(f'{args.out}/git{SUF}-summary.json').read())

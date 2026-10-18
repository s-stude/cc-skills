#!/usr/bin/env python3
"""Token, tool and time analysis of Claude Code transcripts. See ../SKILL.md."""
import argparse, bisect, csv, collections, glob, json, os, re, statistics, sys
from datetime import datetime, timezone, timedelta

ap = argparse.ArgumentParser(description='Analyze Claude Code session transcripts')
ap.add_argument('--projects', nargs='+', required=True, help='transcript dirs or globs under ~/.claude/projects (e.g. "~/.claude/projects/-Users-me-src-app*")')
ap.add_argument('--exclude', nargs='*', default=[], help='substrings; transcript dirs containing any are skipped')
ap.add_argument('--branch-regex', default='.*', help='keep a session if any of its entries records a gitBranch matching this regex')
ap.add_argument('--sessions', nargs='*', default=[], help='keep only these session ids (prefixes ok)')
ap.add_argument('--since', help='ISO date/time; drop calls, prompts and events before it')
ap.add_argument('--until', help='ISO date/time; drop calls, prompts and events after it')
ap.add_argument('--tz', type=float, default=None, help='report timezone as hours offset from UTC (default: local)')
ap.add_argument('--prices', help='JSON file {model: [input, output, cache_read, write_5m, write_1h]} in $/MTok, merged over the defaults')
ap.add_argument('--handoff-regex', default=r'^\s*(# Brief|You are continuing)', help='prompts matching this are agent-written hand-off briefs, not typed by a human')
ap.add_argument('--out', required=True, help='output directory')
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
OUT = args.out
TZ = timezone(timedelta(hours=args.tz)) if args.tz is not None else datetime.now().astimezone().tzinfo
TZNAME = f'UTC{args.tz:+g}' if args.tz is not None else datetime.now().astimezone().strftime('%Z')

PRICE = {  # $/MTok: input, output, cache read, cache write 5m, cache write 1h. Verify against current pricing before trusting.
    'claude-fable-5-1': (10.0, 50.0, 0.25, 12.5, 20.0),
    'claude-fable-5': (10.0, 50.0, 1.00, 12.5, 20.0),
    'claude-opus-5-5': (4.0, 20.0, 0.20, 5.0, 8.0),
    'claude-opus-5': (5.0, 25.0, 0.50, 6.25, 10.0),
    'claude-opus-4-8': (5.0, 25.0, 0.50, 6.25, 10.0),
    'claude-opus-4-7': (5.0, 25.0, 0.50, 6.25, 10.0),
    'claude-opus-4-6': (5.0, 25.0, 0.50, 6.25, 10.0),
    'claude-sonnet-5-5': (2.0, 10.0, 0.20, 2.5, 4.0),
    'claude-sonnet-5': (2.0, 10.0, 0.20, 2.5, 4.0),
    'claude-sonnet-4-6': (3.0, 15.0, 0.30, 3.75, 6.0),
    'claude-haiku-5-5': (0.10, 0.50, 0.01, 0.125, 0.20),
    'claude-haiku-4-5': (1.0, 5.0, 0.10, 1.25, 2.0),
}
if args.prices:
    PRICE.update({k: tuple(v) for k, v in json.load(open(os.path.expanduser(args.prices))).items()})

def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

SINCE = ts(args.since).astimezone(timezone.utc) if args.since and 'T' in args.since else (datetime.fromisoformat(args.since).replace(tzinfo=TZ) if args.since else None)
UNTIL = ts(args.until).astimezone(timezone.utc) if args.until and 'T' in args.until else (datetime.fromisoformat(args.until).replace(tzinfo=TZ) + timedelta(days=1) if args.until else None)
def in_window(T):
    return (SINCE is None or T >= SINCE) and (UNTIL is None or T < UNTIL)

dirs = sorted({d for pat in args.projects for d in glob.glob(os.path.expanduser(pat)) if os.path.isdir(d)})
dirs = [d for d in dirs if not any(e in d for e in args.exclude)]
if not dirs:
    sys.exit('no transcript directories matched --projects')
common = os.path.commonprefix([os.path.basename(d) for d in dirs])
def short_dir(d):
    return d[len(common):].strip('-') or d.split('-')[-1] if len(dirs) > 1 else d

files = []
for d in dirs:
    for f in glob.glob(d + '/*.jsonl'):
        files.append((short_dir(os.path.basename(d)), f, None))
        for s in glob.glob(f[:-6] + '/subagents/*.jsonl'):
            meta = {}
            mp = s[:-6] + '.meta.json'
            if os.path.exists(mp):
                try: meta = json.load(open(mp))
                except Exception: pass
            files.append((short_dir(os.path.basename(d)), s, meta))

calls = {}          # message.id -> call record
tool_uses = {}      # tool_use_id -> record
tool_results = {}   # tool_use_id -> (ts, chars, is_error)
prompts = {}        # uuid -> prompt record
turns = []          # turn_duration
compactions = []
cost_state = {}     # sessionId -> max cost-state
sessions = collections.defaultdict(lambda: dict(dirs=set(), branches=collections.Counter(), title=None, custom=None, first=None, last=None, files=0, subagents=0))
agents = {}         # agent file -> info
events = collections.defaultdict(list)  # session -> timestamps (all files)

for dname, f, meta in files:
    is_sub = meta is not None
    agent_key = os.path.basename(f)[:-6] if is_sub else None
    parent_sid = os.path.basename(os.path.dirname(os.path.dirname(f))) if is_sub else os.path.basename(f)[:-6]
    if is_sub:
        agents[f] = dict(session=parent_sid, agent=agent_key, type=meta.get('agentType'), desc=meta.get('description'), model=meta.get('model'), first=None, last=None, calls=0)
        sessions[parent_sid]['subagents'] += 1
    else:
        sessions[parent_sid]['files'] += 1
    sessions[parent_sid]['dirs'].add(dname)
    for line in open(f):
        try: d = json.loads(line)
        except Exception: continue
        t = d.get('type')
        sid = parent_sid
        S = sessions[sid]
        if d.get('gitBranch'): S['branches'][d['gitBranch']] += 1
        if t == 'ai-title': S['title'] = d['aiTitle']
        if t == 'custom-title': S['custom'] = d['customTitle']
        if t == 'cost-state':
            k = d['sessionId']
            if k not in cost_state or d['totalCostUSD'] >= cost_state[k]['totalCostUSD']:
                cost_state[k] = d
        stamp = d.get('timestamp')
        if stamp and not in_window(ts(stamp)) and t in ('user', 'assistant', 'system'):
            continue
        if stamp and t in ('user', 'assistant', 'system'):
            T = ts(stamp)
            S['first'] = min(S['first'] or T, T); S['last'] = max(S['last'] or T, T)
            events[sid].append(T)
            if is_sub:
                A = agents[f]; A['first'] = min(A['first'] or T, T); A['last'] = max(A['last'] or T, T)
        if t == 'system' and d.get('subtype') == 'turn_duration' and not is_sub and stamp:
            turns.append(dict(session=sid, ts=ts(stamp), ms=d.get('durationMs', 0), uuid=d.get('uuid')))
        if t == 'system' and d.get('subtype') == 'compact_boundary' and stamp:
            cm = d.get('compactMetadata') or {}
            compactions.append(dict(session=sid, ts=ts(stamp), pre=cm.get('preTokens'), trigger=cm.get('trigger'), ms=cm.get('durationMs'), uuid=d.get('uuid')))
        if t == 'assistant':
            m = d['message']; u = m.get('usage') or {}
            mid = m.get('id') or d.get('requestId') or d.get('uuid')
            if m.get('model') == '<synthetic>': continue
            rec = calls.get(mid)
            if rec is None:
                cc = u.get('cache_creation') or {}
                rec = calls[mid] = dict(id=mid, session=sid, sub=is_sub, agent=agent_key, agent_type=(meta or {}).get('agentType'),
                    model=m.get('model'), ts=ts(stamp), input=u.get('input_tokens', 0), output=u.get('output_tokens', 0),
                    cread=u.get('cache_read_input_tokens', 0), cwrite=u.get('cache_creation_input_tokens', 0),
                    w5=cc.get('ephemeral_5m_input_tokens', 0), w1=cc.get('ephemeral_1h_input_tokens', 0),
                    thinking=(u.get('output_tokens_details') or {}).get('thinking_tokens', 0), text_chars=0, content_chars=0, tools=[],
                    branch=d.get('gitBranch'))
                if is_sub: agents[f]['calls'] += 1
            else:
                cc = u.get('cache_creation') or {}
                for k, v in (('input', u.get('input_tokens', 0)), ('output', u.get('output_tokens', 0)), ('cread', u.get('cache_read_input_tokens', 0)),
                             ('cwrite', u.get('cache_creation_input_tokens', 0)), ('w5', cc.get('ephemeral_5m_input_tokens', 0)), ('w1', cc.get('ephemeral_1h_input_tokens', 0)),
                             ('thinking', (u.get('output_tokens_details') or {}).get('thinking_tokens', 0))):
                    rec[k] = max(rec[k], v or 0)
            for b in m.get('content') or []:
                if b.get('type') == 'text':
                    rec['text_chars'] += len(b.get('text', ''))
                    rec['content_chars'] += len(b.get('text', ''))
                elif b.get('type') == 'tool_use':
                    if b['id'] not in tool_uses:
                        rec['content_chars'] += len(json.dumps(b.get('input') or {}, ensure_ascii=False))
                        tool_uses[b['id']] = dict(id=b['id'], name=b.get('name'), input=b.get('input') or {}, ts=ts(stamp), session=sid, sub=is_sub, call=mid)
                        rec['tools'].append(b['id'])
        if t == 'user':
            c = d['message'].get('content')
            if isinstance(c, list):
                for b in c:
                    if b.get('type') == 'tool_result':
                        cont = b.get('content')
                        n = len(cont) if isinstance(cont, str) else sum(len(x.get('text', '')) for x in (cont or []) if isinstance(x, dict))
                        if b['tool_use_id'] not in tool_results:
                            tool_results[b['tool_use_id']] = (ts(stamp), n, bool(b.get('is_error')))
            if not is_sub and not d.get('isMeta') and not d.get('isSidechain') and d.get('origin', {}) and (d.get('origin') or {}).get('kind') == 'human':
                txt = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text')
                if d['uuid'] not in prompts:
                    handoff = bool(re.search(args.handoff_regex, txt))
                    prompts[d['uuid']] = dict(uuid=d['uuid'], session=sid, ts=ts(stamp), text=txt, chars=len(txt), handoff=handoff, slash=txt.lstrip().startswith('<command-'))

BR = re.compile(args.branch_regex)
def related(sid):
    S = sessions[sid]
    if S['first'] is None: return False
    if args.sessions and not any(sid.startswith(p) for p in args.sessions): return False
    return any(BR.search(b) for b in S['branches']) or (args.branch_regex == '.*')
SIDS = sorted([s for s in sessions if related(s)], key=lambda s: sessions[s]['first'])
if not SIDS:
    sys.exit('no sessions matched the filters')

# the same prompt can be logged twice (resume, retry); collapse identical text in one session within 2 minutes
_last = {}
for p in sorted(prompts.values(), key=lambda p: p['ts']):
    k = (p['session'], p['text'])
    if k in _last and (p['ts'] - _last[k]).total_seconds() < 120:
        p['dup'] = True
    _last[k] = p['ts']
prompts = {u: p for u, p in prompts.items() if not p.get('dup')}
unknown = sorted({c['model'] for c in calls.values() if c['model'] not in PRICE and c['session'] in set(SIDS)})
if unknown:
    print('WARNING: no price for models', unknown, '- their cost is counted as $0; pass --prices', file=sys.stderr)
SIDSET = set(SIDS)

def cost(r):
    p = PRICE.get(r['model'])
    if not p: return 0.0
    w5 = r['w5']; w1 = r['w1']
    if w5 + w1 == 0: w5 = r['cwrite']
    return (r['input'] * p[0] + r['output'] * p[1] + r['cread'] * p[2] + w5 * p[3] + w1 * p[4]) / 1e6

for r in calls.values():
    r['cost'] = cost(r)
    r['output_est'] = max(r['output'], round(r['content_chars'] / 3.5))
    p = PRICE.get(r['model'])
    r['cost_est'] = r['cost'] + ((r['output_est'] - r['output']) * p[1] / 1e6 if p else 0)
CALLS = sorted([r for r in calls.values() if r['session'] in SIDSET], key=lambda r: r['ts'])

# attribute each call to the latest human prompt in its session
by_sess_prompts = collections.defaultdict(list)
for p in sorted(prompts.values(), key=lambda p: p['ts']):
    if p['session'] in SIDSET: by_sess_prompts[p['session']].append(p)
for r in CALLS:
    ps = by_sess_prompts.get(r['session'], [])
    i = bisect.bisect_right([p['ts'] for p in ps], r['ts']) - 1
    r['prompt'] = ps[i]['uuid'] if i >= 0 else None

def agg(rows):
    a = collections.Counter()
    for r in rows:
        a['calls'] += 1
        for k in ('input', 'output', 'cread', 'cwrite', 'w5', 'w1', 'thinking', 'text_chars', 'output_est'): a[k] += r[k]
        a['cost'] += r['cost']
        a['cost_est'] += r['cost_est']
        a['tools'] += len(r['tools'])
    a['total'] = a['input'] + a['output'] + a['cread'] + a['cwrite']
    return a

# Bash categorization
CATS = [
    ('git commit', r'\bgit\b[^|;&]*\bcommit\b'),
    ('git push', r'\bgit\b[^|;&]*\bpush\b'),
    ('git rebase/merge/cherry-pick', r'\bgit\b[^|;&]*\b(rebase|merge|cherry-pick|reset|squash)\b'),
    ('git worktree/branch', r'\bgit\b[^|;&]*\b(worktree|branch|checkout|switch)\b'),
    ('e2e / Playwright run', r'playwright|test:e2e|e2e[^ ]*\.sh|apps/e2e.*(bun|npx|run)|bun run e2e|soak'),
    ('unit/integration tests (bun test)', r'\bbun (run )?test\b|turbo run test|bun run test'),
    ('typecheck / lint / build', r'typecheck|\blint\b|\btsc\b|turbo run build|bun run build|eslint'),
    ('docker / mongo', r'\bdocker\b|mongosh|mongod\b'),
    ('process restart / kill / ports', r'\bpkill\b|\bkill\b|lsof|killall|restart'),
    ('install deps', r'bun install|npm i\b|npm install|bunx? add'),
    ('agterm / session control', r'agtermctl'),
    ('revmux / review', r'revmux'),
    ('gh / GitHub', r'(^|\s)gh\s'),
    ('git read (log/diff/status/show)', r'\bgit\b[^|;&]*\b(log|diff|status|show|rev-parse|merge-base|ls-files|blame|stash|fetch|remote|tag|reflog|cat-file|rev-list)\b'),
    ('file read/search (cat/grep/ls/find/sed)', r'^\s*(cd [^;&]+&&\s*)?(cat|head|tail|grep|rg|ls|find|sed|wc|awk|tree|jq|du|stat|file|diff)\b'),
    ('sleep / wait / poll', r'\bsleep\b|\bwait\b|until '),
]
def bash_cat(cmd):
    for name, rx in CATS:
        if re.search(rx, cmd, re.I | re.M): return name
    return 'other shell'

TU = [t for t in tool_uses.values() if t['session'] in SIDSET]
for t in TU:
    res = tool_results.get(t['id'])
    t['dur'] = (res[0] - t['ts']).total_seconds() if res else None
    t['res_chars'] = res[1] if res else 0
    t['err'] = res[2] if res else None
    if t['name'] == 'Bash':
        t['cat'] = bash_cat(t['input'].get('command', ''))
        t['bg'] = bool(t['input'].get('run_in_background'))
    else:
        t['cat'] = None

def fmt(n): return f'{n:,.0f}'
def fm(n): return f'${n:,.2f}'
def hm(sec):
    sec = int(sec); return f'{sec // 3600}h {sec % 3600 // 60:02d}m'

L = []
w = L.append

# ---------- overall ----------
A = agg(CALLS)
w('## 1. Token totals (all selected sessions, main threads + subagents)\n')
w('| Metric | Tokens |')
w('|---|---:|')
w(f"| API calls (unique responses) | {fmt(A['calls'])} |")
w(f"| Uncached input | {fmt(A['input'])} |")
w(f"| Cache write (total) | {fmt(A['cwrite'])} |")
w(f"| &nbsp;&nbsp;of which 1h TTL | {fmt(A['w1'])} |")
w(f"| &nbsp;&nbsp;of which 5m TTL | {fmt(A['w5'])} |")
w(f"| Cache read | {fmt(A['cread'])} |")
w(f"| Output (incl. thinking) | {fmt(A['output'])} |")
w(f"| &nbsp;&nbsp;of which thinking (where reported) | {fmt(A['thinking'])} |")
w(f"| **All tokens processed** | **{fmt(A['total'])}** |")
w(f"| Output re-estimated from visible content length (corrects subagent stream-start placeholders, see §0) | {fmt(A['output_est'])} |")
w(f"| Tool calls issued | {fmt(A['tools'])} |")
w(f"| Estimated API-list-price cost (recorded usage) | **{fm(A['cost'])}** |")
w(f"| Same, with re-estimated output | {fm(A['cost_est'])} |")
cs_total = sum(v['totalCostUSD'] for k, v in cost_state.items() if k in SIDSET)
w(f"| Claude Code's own `cost-state` total (sessions that recorded one) | {fm(cs_total)} |\n")
w(f"Cache hit ratio (read / (read + write + uncached input)): **{A['cread'] / max(1, A['cread'] + A['cwrite'] + A['input']):.1%}**. "
  f"Input-side tokens are {(A['input'] + A['cread'] + A['cwrite']) / max(1, A['output']):,.0f}x the output tokens.\n")

# by model / main vs sub
w('### 1.1 By model and thread kind\n')
w('| Model | Thread | Calls | Uncached in | Cache write | Cache read | Output (recorded) | Output (est.) | Total | Cost |')
w('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
grp = collections.defaultdict(list)
for r in CALLS: grp[(r['model'], 'subagent' if r['sub'] else 'main')].append(r)
for k in sorted(grp, key=lambda k: -agg(grp[k])['cost']):
    a = agg(grp[k])
    w(f"| {k[0]} | {k[1]} | {fmt(a['calls'])} | {fmt(a['input'])} | {fmt(a['cwrite'])} | {fmt(a['cread'])} | {fmt(a['output'])} | {fmt(a['output_est'])} | {fmt(a['total'])} | {fm(a['cost'])} |")
w('')
w('### 1.2 By subagent type\n')
w('| Agent type | Agents spawned | Calls | Total tokens | Output | Cost |')
w('|---|---:|---:|---:|---:|---:|')
at = collections.defaultdict(list)
for r in CALLS:
    if r['sub']: at[r['agent_type'] or '?'].append(r)
ag_count = collections.Counter(a['type'] or '?' for a in agents.values() if a['session'] in SIDSET)
for k in sorted(at, key=lambda k: -agg(at[k])['cost']):
    a = agg(at[k])
    w(f"| {k} | {ag_count[k]} | {fmt(a['calls'])} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} |")
w('')

# by day
w(f'### 1.3 By day ({TZNAME})\n')
w('| Day | Calls | Total tokens | Output | Cost | Human prompts |')
w('|---|---:|---:|---:|---:|---:|')
dd = collections.defaultdict(list)
for r in CALLS: dd[r['ts'].astimezone(TZ).strftime('%a %Y-%m-%d')].append(r)
pd = collections.Counter(p['ts'].astimezone(TZ).strftime('%a %Y-%m-%d') for s in SIDS for p in by_sess_prompts[s] if not p['handoff'])
for k in sorted(dd, key=lambda k: k[4:]):
    a = agg(dd[k])
    w(f"| {k} | {fmt(a['calls'])} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} | {pd[k]} |")
w('')

# by branch
w('### 1.4 By git branch (branch recorded on each API call)\n')
w('| Branch | Calls | Total tokens | Output | Cost |')
w('|---|---:|---:|---:|---:|')
bb = collections.defaultdict(list)
for r in CALLS: bb[r['branch'] or '(none recorded: subagent/side thread)'].append(r)
for k in sorted(bb, key=lambda k: -agg(bb[k])['cost']):
    a = agg(bb[k])
    w(f"| `{k}` | {fmt(a['calls'])} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} |")
w('')

# ---------- sessions ----------
w('## 2. Per session\n')
w('Sessions ordered by start. "Active" is the sum of Claude Code `turn_duration` records (main thread working on a prompt). Subagent tokens are included in the session row.\n')
w(f'| # | Session | Folder | Main branch | Title | Start ({TZNAME}) | End ({TZNAME}) | Prompts | Subagents | Calls | Total tokens | Output | Cost | Active |')
w('|---:|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|')
sess_calls = collections.defaultdict(list)
for r in CALLS: sess_calls[r['session']].append(r)
turn_ms = collections.Counter()
for t in turns:
    if t['session'] in SIDSET: turn_ms[t['session']] += t['ms']
for i, s in enumerate(SIDS, 1):
    S = sessions[s]; a = agg(sess_calls[s])
    title = (('[' + S['custom'] + '] ') if S['custom'] else '') + (S['title'] or '')
    br = S['branches'].most_common(1)[0][0] if S['branches'] else ''
    np = len([p for p in by_sess_prompts[s] if not p['handoff']])
    w(f"| {i} | `{s[:8]}` | {'/'.join(sorted(S['dirs']))} | `{br}` | {title.replace('|', '/')[:60]} | {S['first'].astimezone(TZ):%m-%d %H:%M} | {S['last'].astimezone(TZ):%m-%d %H:%M} | {np} | {S['subagents']} | {fmt(a['calls'])} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} | {hm(turn_ms[s] / 1000)} |")
w('')

# ---------- tools ----------
w('## 3. Tool calls\n')
w('Result size is the text returned to the model (≈ chars/4 tokens), which then rides along in every later request of that thread until compaction.\n')
w('| Tool | Calls | In subagents | Errors | Total wall time | Median | Result chars | ≈ Result tokens |')
w('|---|---:|---:|---:|---:|---:|---:|---:|')
tg = collections.defaultdict(list)
for t in TU: tg[t['name']].append(t)
for k in sorted(tg, key=lambda k: -len(tg[k])):
    ts_ = tg[k]; durs = [t['dur'] for t in ts_ if t['dur'] is not None and t['dur'] >= 0]
    rc = sum(t['res_chars'] for t in ts_)
    w(f"| {k} | {len(ts_)} | {sum(t['sub'] for t in ts_)} | {sum(1 for t in ts_ if t['err'])} | {hm(sum(durs))} | {statistics.median(durs) if durs else 0:.1f}s | {fmt(rc)} | {fmt(rc / 4)} |")
w('')
w('### 3.1 Bash commands by purpose\n')
w('Background commands (`run_in_background`) return immediately, so their wall time is not measured here; long e2e soaks were mostly run that way.\n')
w('| Purpose | Commands | Background | In subagents | Foreground wall time | Longest | Result chars |')
w('|---|---:|---:|---:|---:|---:|---:|')
bg = collections.defaultdict(list)
for t in TU:
    if t['name'] == 'Bash': bg[t['cat']].append(t)
for k in sorted(bg, key=lambda k: -sum((t['dur'] or 0) for t in bg[k] if not t['bg'])):
    ts_ = bg[k]; durs = [t['dur'] for t in ts_ if t['dur'] is not None and t['dur'] >= 0 and not t['bg']]
    w(f"| {k} | {len(ts_)} | {sum(t['bg'] for t in ts_)} | {sum(t['sub'] for t in ts_)} | {hm(sum(durs))} | {hm(max(durs) if durs else 0)} | {fmt(sum(t['res_chars'] for t in ts_))} |")
w('')

# files touched by Edit/Write
w('### 3.2 Files edited or written by agents (top 40 by edit count)\n')
fe = collections.Counter(); fw = collections.Counter()
for t in TU:
    if t['name'] in ('Edit', 'MultiEdit', 'NotebookEdit'): fe[t['input'].get('file_path', '?')] += 1
    if t['name'] == 'Write': fw[t['input'].get('file_path', '?')] += 1
allf = collections.Counter(); allf.update(fe); allf.update(fw)
w(f'{len(allf)} distinct files were edited or written ({sum(fe.values())} Edit calls, {sum(fw.values())} Write calls).\n')
w('| File | Edits | Writes |')
w('|---|---:|---:|')
for k, _ in allf.most_common(40):
    kk = k.replace(os.path.expanduser('~'), '~')
    kk = re.sub(r'^/private/tmp/claude-501/[^/]+/[^/]+/scratchpad/', '(scratchpad)/', kk)
    w(f'| `{kk}` | {fe[k]} | {fw[k]} |')
w('')

# ---------- time ----------
HP = [p for s in SIDS for p in by_sess_prompts[s]]
HPh = [p for p in HP if not p['handoff']]
allT = sorted(T for s in SIDS for T in events[s])
start, end = allT[0], allT[-1]

def union(intervals):
    tot = 0; cur = None
    for a, b in sorted(intervals):
        if cur is None or a > cur[1]:
            if cur: tot += (cur[1] - cur[0]).total_seconds()
            cur = [a, b]
        else: cur[1] = max(cur[1], b)
    if cur: tot += (cur[1] - cur[0]).total_seconds()
    return tot

# activity intervals: consecutive events < 10 min apart form a block
def blocks(times, gap):
    out = []; times = sorted(times)
    if not times: return out
    a = b = times[0]
    for T in times[1:]:
        if (T - b).total_seconds() > gap: out.append((a, b)); a = T
        b = T
    out.append((a, b)); return out

agent_turn_intervals = [(t['ts'] - timedelta(milliseconds=t['ms']), t['ts']) for t in turns if t['session'] in SIDSET]
sub_intervals = [(a['first'], a['last']) for a in agents.values() if a['session'] in SIDSET and a['first']]
any_events = blocks(allT, 600)
human_blocks = blocks([p['ts'] for p in HPh], 1800)

# human think/read/type gaps: from end of the previous turn in the same session to the next prompt
turn_by_sess = collections.defaultdict(list)
for t in turns:
    if t['session'] in SIDSET: turn_by_sess[t['session']].append(t['ts'])
gaps = []
for s in SIDS:
    ends = sorted(turn_by_sess[s])
    for p in by_sess_prompts[s]:
        if p['handoff']: continue
        i = bisect.bisect_left(ends, p['ts']) - 1
        if i >= 0:
            g = (p['ts'] - ends[i]).total_seconds()
            if g >= 0: gaps.append(g)
gaps_capped = [min(g, 900) for g in gaps]
typed_chars = sum(p['chars'] for p in HPh if not p['slash'])
shown_chars = sum(r['text_chars'] for r in CALLS if not r['sub'])

w('## 4. Time\n')
w(f"* First recorded event: **{start.astimezone(TZ):%a %Y-%m-%d %H:%M}** {TZNAME}. Last: **{end.astimezone(TZ):%a %Y-%m-%d %H:%M}** {TZNAME}.")
w(f"* Calendar span: **{(end - start).total_seconds() / 3600:,.1f} h** ({(end - start).days} days {((end - start).seconds) // 3600} h).")
w(f"* Wall-clock time with any Claude activity (union of all sessions, events < 10 min apart merged): **{hm(sum((b - a).total_seconds() for a, b in any_events))}** in {len(any_events)} blocks.")
w(f"* Wall-clock time the main agent threads were working (union of `turn_duration` intervals): **{hm(union(agent_turn_intervals))}**.")
w(f"* Same, summed per session (parallel sessions count twice): **{hm(sum(t['ms'] for t in turns if t['session'] in SIDSET) / 1000)}** over {len(agent_turn_intervals)} turns.")
w(f"* Subagent lifetimes summed: **{hm(sum((b - a).total_seconds() for a, b in sub_intervals))}** over {len(sub_intervals)} subagents; union with main threads: **{hm(union(agent_turn_intervals + sub_intervals))}**.")
w(f"* Human prompts typed: **{len(HPh)}** (+ {len(HP) - len(HPh)} pasted hand-off briefs), {sum(p['slash'] for p in HPh)} of them slash commands; {fmt(typed_chars)} characters typed in total.")
w(f"* Human engagement blocks (prompts < 30 min apart): **{hm(sum((b - a).total_seconds() for a, b in human_blocks))}** in {len(human_blocks)} blocks (lower bound: excludes reading after the last prompt of a block).")
w(f"* Think/read/type gaps (end of agent turn → next prompt in that session): {len(gaps)} gaps, median **{statistics.median(gaps):.0f} s**, sum capped at 15 min each **{hm(sum(gaps_capped))}**, uncapped {hm(sum(gaps))}.")
w(f"* Estimated pure typing at 40 wpm (≈200 chars/min): **{hm(typed_chars / 200 * 60)}**. Estimated reading of all main-thread text Claude printed ({fmt(shown_chars)} chars) at 250 wpm (≈1,250 chars/min): **{hm(shown_chars / 1250 * 60)}**.\n")

w('### 4.1 Per day\n')
w(f'| Day ({TZNAME}) | First | Last | Activity blocks | Agent-working (union) | Human prompts | Human engaged |')
w('|---|---|---|---:|---:|---:|---:|')
days = sorted({T.astimezone(TZ).date() for T in allT})
for dday in days:
    ev = [b for b in any_events if b[0].astimezone(TZ).date() == dday]
    at_ = [i for i in agent_turn_intervals if i[1].astimezone(TZ).date() == dday]
    hb = [b for b in human_blocks if b[0].astimezone(TZ).date() == dday]
    dt = [T for T in allT if T.astimezone(TZ).date() == dday]
    w(f"| {dday:%a %m-%d} | {min(dt).astimezone(TZ):%H:%M} | {max(dt).astimezone(TZ):%H:%M} | {hm(sum((b - a).total_seconds() for a, b in ev))} | {hm(union(at_))} | {len([p for p in HPh if p['ts'].astimezone(TZ).date() == dday])} | {hm(sum((b - a).total_seconds() for a, b in hb))} |")
w('')
w(f'### 4.2 Hour-of-day heatmap (human prompts, {TZNAME})\n')
hh = collections.Counter(p['ts'].astimezone(TZ).hour for p in HPh)
w('| Hour | ' + ' | '.join(f'{h:02d}' for h in range(24)) + ' |')
w('|---|' + '---:|' * 24)
w('| Prompts | ' + ' | '.join(str(hh[h]) for h in range(24)) + ' |\n')

w('### 4.3 Compactions\n')
CP = [c for c in compactions if c['session'] in SIDSET]
cpu = {c['uuid']: c for c in CP}.values()
w(f"{len(cpu)} context compactions; {sum(1 for c in cpu if c['trigger'] == 'auto')} automatic. Pre-compaction context sizes: "
  + ', '.join(fmt(c['pre'] or 0) for c in sorted(cpu, key=lambda c: c['ts'])) + '. '
  + f"Time spent compacting: {hm(sum((c['ms'] or 0) for c in cpu) / 1000)}.\n")

# ---------- top prompts ----------
w('## 5. Most expensive human requests (top 40)\n')
w('Tokens of every API call (main thread and its subagents) from the prompt until the next prompt in the same session.\n')
pc = collections.defaultdict(list)
for r in CALLS: pc[r['prompt']].append(r)
w(f'| # | When ({TZNAME}) | Session | Prompt (first 90 chars) | Calls | Subagent calls | Total tokens | Output | Cost |')
w('|---:|---|---|---|---:|---:|---:|---:|---:|')
pr = {p['uuid']: p for p in HP}
ranked = sorted([k for k in pc if k], key=lambda k: -agg(pc[k])['cost'])
for i, k in enumerate(ranked[:40], 1):
    p = pr[k]; a = agg(pc[k])
    txt = re.sub(r'\s+', ' ', p['text'])[:90].replace('|', '/').replace('<', '&lt;')
    w(f"| {i} | {p['ts'].astimezone(TZ):%m-%d %H:%M} | `{p['session'][:8]}` | {txt} | {a['calls']} | {sum(r['sub'] for r in pc[k])} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} |")
w('')

# ---------- full per-prompt list ----------
w('## Appendix A. Every human request\n')
w('All prompts in chronological order with the tokens they triggered. `H` = hand-off brief pasted into a new worktree session.\n')
w(f'| # | When ({TZNAME}) | Session | Prompt (first 70 chars) | Calls | Tools | Total tokens | Output | Cost |')
w('|---:|---|---|---|---:|---:|---:|---:|---:|')
for i, p in enumerate(sorted(HP, key=lambda p: p['ts']), 1):
    a = agg(pc.get(p['uuid'], []))
    txt = re.sub(r'\s+', ' ', p['text'])[:70].replace('|', '/').replace('<', '&lt;')
    w(f"| {i}{' H' if p['handoff'] else ''} | {p['ts'].astimezone(TZ):%m-%d %H:%M} | `{p['session'][:8]}` | {txt} | {a['calls']} | {a['tools']} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} |")
pre = agg(pc.get(None, []))
w(f"\nCalls before any human prompt in their session (e.g. resumed or forked threads): {pre['calls']} calls, {fmt(pre['total'])} tokens, {fm(pre['cost'])}.\n")

# ---------- subagents ----------
w('## Appendix B. Every subagent\n')
w(f'| Session | Agent | Type | Model | Description | Start ({TZNAME}) | Lifetime | Calls | Total tokens | Output | Cost |')
w('|---|---|---|---|---|---|---:|---:|---:|---:|---:|')
ac = collections.defaultdict(list)
for r in CALLS:
    if r['sub']: ac[(r['session'], r['agent'])].append(r)
for f, A_ in sorted(agents.items(), key=lambda kv: kv[1]['first'] or start):
    if A_['session'] not in SIDSET or not A_['first']: continue
    a = agg(ac[(A_['session'], A_['agent'])])
    models = ','.join(sorted({r['model'].replace('claude-', '') for r in ac[(A_['session'], A_['agent'])]}))
    w(f"| `{A_['session'][:8]}` | `{A_['agent'][6:14]}` | {A_['type']} | {models} | {(A_['desc'] or '').replace('|', '/')[:60]} | {A_['first'].astimezone(TZ):%m-%d %H:%M} | {hm((A_['last'] - A_['first']).total_seconds())} | {a['calls']} | {fmt(a['total'])} | {fmt(a['output'])} | {fm(a['cost'])} |")
w('')

open(OUT + '/sessions.md', 'w').write('\n'.join(L))

with open(OUT + '/calls.csv', 'w', newline='') as fh:
    cw = csv.writer(fh)
    cw.writerow(['timestamp_utc', 'session', 'thread', 'agent', 'agent_type', 'model', 'branch', 'input', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'output', 'thinking', 'tool_calls', 'tools', 'cost_usd', 'prompt_uuid'])
    for r in CALLS:
        cw.writerow([r['ts'].isoformat(), r['session'], 'subagent' if r['sub'] else 'main', r['agent'] or '', r['agent_type'] or '', r['model'], r['branch'] or '',
                     r['input'], r['w5'] if r['w5'] + r['w1'] else r['cwrite'], r['w1'], r['cread'], r['output'], r['thinking'], len(r['tools']),
                     ';'.join(tool_uses[x]['name'] for x in r['tools']), f"{r['cost']:.6f}", r['prompt'] or ''])
with open(OUT + '/tools.csv', 'w', newline='') as fh:
    cw = csv.writer(fh)
    cw.writerow(['timestamp_utc', 'session', 'thread', 'tool', 'bash_category', 'background', 'duration_s', 'result_chars', 'is_error', 'summary'])
    for t in sorted(TU, key=lambda t: t['ts']):
        inp = t['input']
        summ = inp.get('command') or inp.get('file_path') or inp.get('pattern') or inp.get('description') or inp.get('skill') or ''
        cw.writerow([t['ts'].isoformat(), t['session'], 'subagent' if t['sub'] else 'main', t['name'], t['cat'] or '', t.get('bg', ''), '' if t['dur'] is None else f"{t['dur']:.1f}",
                     t['res_chars'], t['err'], re.sub(r'\s+', ' ', str(summ))[:300]])

json.dump(dict(sessions=len(SIDS), calls=A['calls'], total=A['total'], cost=A['cost'], cs_total=cs_total,
               cs_lines_added=sum(v.get('totalLinesAdded', 0) for k, v in cost_state.items() if k in SIDSET),
               cs_lines_removed=sum(v.get('totalLinesRemoved', 0) for k, v in cost_state.items() if k in SIDSET),
               cs_sessions=len([k for k in cost_state if k in SIDSET]),
               subagents=len([a for a in agents.values() if a['session'] in SIDSET]),
               prompts=len(HPh), handoffs=len(HP) - len(HPh), start=start.isoformat(), end=end.isoformat(),
               excluded=[s for s in sessions if s not in SIDSET]), open(OUT + '/summary.json', 'w'), indent=1, default=str)
print(open(OUT + '/summary.json').read())

#!/usr/bin/env python3
"""List Claude Code transcript folders and sessions for a project path, to decide the analysis scope. See ../SKILL.md."""
import argparse, collections, glob, json, os, re
from datetime import datetime

ap = argparse.ArgumentParser()
ap.add_argument('--path', default='.', help='project directory; its transcript folder and those of sibling worktrees are listed')
ap.add_argument('--siblings', action='store_true', help='also match folders of directories next to --path that share its name as a prefix (e.g. app, app-worktree-x, app-main)')
ap.add_argument('--projects', nargs='*', help='explicit transcript dirs/globs instead of --path')
args = ap.parse_args()

ROOT = os.path.expanduser('~/.claude/projects')
def encode(p):
    return re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(os.path.expanduser(p)))

if args.projects:
    dirs = sorted({d for pat in args.projects for d in glob.glob(os.path.expanduser(pat)) if os.path.isdir(d)})
else:
    enc = encode(args.path)
    pat = enc + '*' if args.siblings else enc
    dirs = sorted(d for d in glob.glob(os.path.join(ROOT, pat)) if os.path.isdir(d))
    if not args.siblings:
        dirs += sorted(d for d in glob.glob(os.path.join(ROOT, enc + '--claude-worktrees-*')) if os.path.isdir(d))
print(f'{len(dirs)} transcript folder(s)')
for d in dirs:
    sess = glob.glob(d + '/*.jsonl')
    subs = glob.glob(d + '/*/subagents/*.jsonl')
    mb = sum(os.path.getsize(f) for f in sess + subs) / 1e6
    print(f'\n== {os.path.basename(d)}  sessions={len(sess)} subagents={len(subs)} size={mb:.1f}MB')
    rows = []
    for f in sess:
        br = collections.Counter(); first = last = None; title = custom = None; prompts = 0; cwd = None
        for line in open(f):
            try: e = json.loads(line)
            except Exception: continue
            if e.get('gitBranch'): br[e['gitBranch']] += 1
            if e.get('cwd'): cwd = e['cwd']
            t = e.get('timestamp')
            if t and e.get('type') in ('user', 'assistant', 'system'):
                first = min(first or t, t); last = max(last or t, t)
            if e.get('type') == 'ai-title': title = e['aiTitle']
            if e.get('type') == 'custom-title': custom = e['customTitle']
            if e.get('type') == 'user' and (e.get('origin') or {}).get('kind') == 'human' and not e.get('isMeta'): prompts += 1
        rows.append((first or '', os.path.basename(f)[:8], last or '', prompts, dict(br.most_common(4)), (f'[{custom}] ' if custom else '') + (title or ''), cwd))
    for r in sorted(rows):
        print(f'  {r[1]}  {r[0][:16]} → {r[2][:16]} UTC  prompts={r[3]:<3} branches={r[4]}  {r[5][:60]}')

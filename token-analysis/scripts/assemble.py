#!/usr/bin/env python3
"""Join the hand-written header with the generated sections into one report. See ../SKILL.md."""
import argparse, os, shutil

ap = argparse.ArgumentParser()
ap.add_argument('--header', required=True, help='markdown with title, scope/method and executive summary (written by Claude)')
ap.add_argument('--work', required=True, help='directory holding sessions.md and optionally git.md / git_appendix.md (one per repo: git*.md)')
ap.add_argument('--report', required=True, help='output markdown path')
ap.add_argument('--csv-dir', help='copy calls.csv and tools.csv here as <report-stem>-calls.csv / -tools.csv')
args = ap.parse_args()

def read(p):
    return open(p).read() if os.path.exists(p) else ''

sess = read(os.path.join(args.work, 'sessions.md'))
main, _, app = sess.partition('## Appendix A')
gits = sorted(f for f in os.listdir(args.work) if f.startswith('git') and f.endswith('.md') and not f.endswith('appendix.md'))
apps = sorted(f for f in os.listdir(args.work) if f.startswith('git') and f.endswith('appendix.md'))
parts = [read(args.header).rstrip() + '\n', main.rstrip() + '\n']
parts += [read(os.path.join(args.work, f)).rstrip() + '\n' for f in gits]
if app:
    parts.append('## Appendix A' + app.rstrip() + '\n')
parts += [read(os.path.join(args.work, f)).rstrip() + '\n' for f in apps]
open(args.report, 'w').write('\n'.join(parts))
print('wrote', args.report)
if args.csv_dir:
    os.makedirs(args.csv_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.report))[0]
    for n in ('calls', 'tools'):
        src = os.path.join(args.work, f'{n}.csv')
        if os.path.exists(src):
            shutil.copy(src, os.path.join(args.csv_dir, f'{stem}-{n}.csv'))
            print('wrote', os.path.join(args.csv_dir, f'{stem}-{n}.csv'))

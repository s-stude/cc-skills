#!/usr/bin/env python3
"""Collect the review scope of a git diff, with moves paired and stale references found.

Usage:
  diff_scope.py [--base REF | --cached | --range A..B] [--save DIR] [--since DIR]
                [--context N] [--max-lines N]

Default scope is the working tree against HEAD, including untracked files.
Sections printed:
  FILES   every changed file with status (M, A, D, ?? untracked, MOVED old -> new)
  MOVES   deleted files paired with their new copy, and only the drift between them
  STALE   references anywhere in the repo that still resolve to a deleted/moved path
  NEXT    commands to see the remaining diffs without the moved files' full deletions
--save DIR   snapshot the current content of every changed file for a later re-review
--since DIR  show what changed in the scope since that snapshot (for re-reviews)
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

DOC_EXT = (".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc")


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def parse_args():
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--base", default="HEAD")
    g.add_argument("--cached", action="store_true")
    g.add_argument("--range")
    p.add_argument("--save")
    p.add_argument("--since")
    p.add_argument("--context", type=int, default=2)
    p.add_argument("--max-lines", type=int, default=120)
    p.add_argument("-h", "--help", action="store_true")
    a = p.parse_args()
    if a.help:
        print(__doc__)
        sys.exit(0)
    return a


class Scope:
    def __init__(self, a):
        self.worktree = not a.cached and not a.range
        if a.range:
            base, _, head = a.range.replace("...", "..").partition("..")
            self.old_rev = git("merge-base", base, head or "HEAD").strip() if "..." in a.range else base
            self.new_rev = head or "HEAD"
            self.diff_args = [a.range]
        elif a.cached:
            self.old_rev, self.new_rev, self.diff_args = "HEAD", ":0", ["--cached"]
        else:
            self.old_rev, self.new_rev, self.diff_args = a.base, None, [a.base]

    def old(self, path):
        return git("show", f"{self.old_rev}:{path}", check=False)

    def new(self, path):
        if self.new_rev is None:
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    return fh.read()
            except OSError:
                return ""
        rev = ":" if self.new_rev == ":0" else f"{self.new_rev}:"
        return git("show", f"{rev}{path}", check=False)


def collect(scope):
    entries = []
    for line in git("diff", "--name-status", "-M", *scope.diff_args).splitlines():
        parts = line.split("\t")
        st = parts[0][0]
        if st == "R":
            entries.append(("R", parts[1], parts[2]))
        else:
            entries.append((st, None, parts[1]))
    if scope.worktree:
        for path in git("ls-files", "--others", "--exclude-standard").splitlines():
            entries.append(("??", None, path))
    return entries


def similarity(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a[:20000], b[:20000], autojunk=False).quick_ratio()


def pair_moves(entries, scope):
    deleted = [e[2] for e in entries if e[0] == "D"]
    added = [e[2] for e in entries if e[0] in ("A", "??")]
    moves, used = [], set()
    for d in deleted:
        base = os.path.basename(d)
        parent = os.path.basename(os.path.dirname(d))
        cands = [x for x in added if x not in used and os.path.basename(x) == base]
        if not cands:
            continue
        old_text = scope.old(d)
        best = max(cands, key=lambda x: (os.path.basename(os.path.dirname(x)) == parent,
                                         similarity(old_text, scope.new(x))))
        if similarity(old_text, scope.new(best)) >= 0.5:
            moves.append((d, best))
            used.add(best)
    moves += [(e[1], e[2]) for e in entries if e[0] == "R"]
    return moves


def drift(scope, old_path, new_path, context, max_lines):
    a, b = scope.old(old_path).splitlines(), scope.new(new_path).splitlines()
    out = list(difflib.unified_diff(a, b, f"old/{old_path}", f"new/{new_path}", n=context, lineterm=""))
    if not out:
        return ["  (identical)"]
    changed = sum(1 for l in out[2:] if l[:1] in "+-")
    head = [f"  {changed} changed line(s)"]
    if len(out) > max_lines:
        return head + out[:max_lines] + [f"  ... truncated, {len(out) - max_lines} more diff lines"]
    return head + out


def stale_refs(scope, gone):
    hits = []
    live_rev = None if scope.worktree else scope.new_rev
    for old_path in gone:
        base = os.path.basename(old_path)
        if live_rev is None:
            args = ["grep", "-n", "-I", "--untracked", "-F", "-e", base]
        elif live_rev == ":0":
            args = ["grep", "-n", "-I", "--cached", "-F", "-e", base]
        else:
            args = ["grep", "-n", "-I", "-F", "-e", base, live_rev]
        r = subprocess.run(["git", *args], capture_output=True, text=True)
        if r.returncode > 1:
            sys.exit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        token = re.compile(r"[\w./~-]*" + re.escape(base))
        for line in r.stdout.splitlines():
            if live_rev and live_rev != ":0" and line.startswith(live_rev + ":"):
                line = line[len(live_rev) + 1:]
            path, _, rest = line.partition(":")
            no, _, text = rest.partition(":")
            for tok in token.findall(text):
                for root in (os.path.dirname(path), ""):
                    resolved = os.path.normpath(os.path.join(root, tok.lstrip("/")))
                    if resolved == old_path and not os.path.exists(os.path.join(root, tok)):
                        hits.append((path, no, tok, old_path))
                        break
    return sorted(set(hits))


def snapshot_files(entries, moves):
    moved_old = {m[0] for m in moves}
    return sorted(e[2] for e in entries if e[0] != "D" and e[2] not in moved_old)


def save(dirpath, scope, files):
    shutil.rmtree(dirpath, ignore_errors=True)
    os.makedirs(os.path.join(dirpath, "files"))
    manifest = {}
    for f in files:
        text = scope.new(f)
        dest = os.path.join(dirpath, "files", f)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        manifest[f] = hashlib.sha256(text.encode()).hexdigest()
    with open(os.path.join(dirpath, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)


def since(dirpath, scope, files, context, max_lines):
    with open(os.path.join(dirpath, "manifest.json")) as fh:
        prev = json.load(fh)
    out, current = [], set(files)
    for f in files:
        text = scope.new(f)
        if f not in prev:
            out.append(f"NEW IN SCOPE {f}")
        elif hashlib.sha256(text.encode()).hexdigest() != prev[f]:
            with open(os.path.join(dirpath, "files", f), encoding="utf-8") as fh:
                old = fh.read().splitlines()
            d = list(difflib.unified_diff(old, text.splitlines(), f"last-pass/{f}", f"now/{f}",
                                          n=context, lineterm=""))
            out.append(f"CHANGED {f}")
            out += d[:max_lines] + ([f"  ... truncated, {len(d) - max_lines} more"] if len(d) > max_lines else [])
    for f in sorted(set(prev) - current):
        out.append(f"LEFT SCOPE {f} (committed, reverted or deleted)")
    return out or ["(nothing changed since the last pass)"]


def main():
    a = parse_args()
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    scope = Scope(a)
    entries = collect(scope)
    moves = pair_moves(entries, scope)
    moved_old = {m[0] for m in moves}
    moved_new = {m[1] for m in moves}

    print("== FILES")
    for st, src, path in entries:
        if path in moved_old or path in moved_new:
            continue
        kind = "doc" if path.lower().endswith(DOC_EXT) else "code"
        print(f"{st:>3} {kind:4} {path}")
    for old_path, new_path in moves:
        kind = "doc" if new_path.lower().endswith(DOC_EXT) else "code"
        print(f"MOVED {kind:4} {old_path} -> {new_path}")

    if moves:
        print("\n== MOVES (drift between old and new copy)")
        for old_path, new_path in moves:
            print(f"-- {old_path} -> {new_path}")
            print("\n".join(drift(scope, old_path, new_path, a.context, a.max_lines)))

    gone = sorted(moved_old | {e[2] for e in entries if e[0] == "D"})
    print("\n== STALE (references still resolving to a deleted or moved path)")
    refs = stale_refs(scope, gone) if gone else []
    for path, no, tok, old_path in refs:
        print(f"{path}:{no}: {tok}  (-> {old_path})")
    if not refs:
        print("(none)" if gone else "(no deleted or moved files)")

    files = snapshot_files(entries, moves)
    modified = [e[2] for e in entries if e[0] in ("M", "A", "T")]
    untracked = [e[2] for e in entries if e[0] == "??" and e[2] not in moved_new]
    deleted = [e[2] for e in entries if e[0] == "D" and e[2] not in moved_old]
    print("\n== NEXT")
    if modified:
        print("Changed-file diffs (moved files excluded):")
        print("  git diff " + " ".join(scope.diff_args) + " -- " + " ".join(modified))
    if untracked:
        print("New untracked files to read in full: " + " ".join(untracked))
    if deleted:
        print("Deleted without a new copy (confirm intended): " + " ".join(deleted))

    if a.since:
        print(f"\n== SINCE LAST PASS ({a.since})")
        print("\n".join(since(a.since, scope, files, a.context, a.max_lines)))
    if a.save:
        save(a.save, scope, files)
        print(f"\n(snapshot of {len(files)} file(s) saved to {a.save})")


if __name__ == "__main__":
    main()

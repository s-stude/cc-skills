#!/usr/bin/env python3
"""Report Markdown links and anchors that don't resolve.

Usage: check_links.py <file-or-dir> [...] [--root <dir>]

Checks inline links, images and reference definitions. External URLs are skipped.
Root-relative links (/path) resolve against --root (default: git top level or cwd).
Exit code 1 when problems are found.
"""
import os
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote

INLINE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'(][^)]*)?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]*>|\S+)")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ID = re.compile(r"""<[^>]+\b(?:id|name)\s*=\s*["']([^"']+)["']""", re.I)
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
INLINE_CODE = re.compile(r"`+[^`]*`+")
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)

_anchor_cache = {}


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip().lower()
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch in " -_" or cat[0] in "LN" or cat == "Mn":
            out.append(ch)
    return "".join(out).replace(" ", "-")


def markdown_lines(path):
    in_fence = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for no, line in enumerate(fh, 1):
            m = FENCE.match(line)
            if m:
                if in_fence is None:
                    in_fence = m.group(1)
                elif m.group(1) == in_fence:
                    in_fence = None
                continue
            if in_fence is None:
                yield no, line.rstrip("\n")


def anchors_for(path):
    if path in _anchor_cache:
        return _anchor_cache[path]
    seen, anchors = {}, set()
    for _, line in markdown_lines(path):
        for hid in HTML_ID.findall(line):
            anchors.add(hid)
        m = HEADING.match(line)
        if not m:
            continue
        base = slugify(m.group(2))
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchors.add(base if n == 0 else f"{base}-{n}")
    _anchor_cache[path] = anchors
    return anchors


def check_target(src, target, root):
    target = target.strip("<>")
    if not target or EXTERNAL.match(target) or target.startswith("//"):
        return None
    path_part, _, anchor = target.partition("#")
    path_part = unquote(path_part.split("?", 1)[0])
    if not path_part:
        dest = src
    elif path_part.startswith("/"):
        dest = os.path.normpath(os.path.join(root, path_part.lstrip("/")))
    else:
        dest = os.path.normpath(os.path.join(os.path.dirname(src), path_part))
    if not os.path.exists(dest):
        return f"missing file: {target}"
    if anchor and os.path.isfile(dest) and dest.lower().endswith((".md", ".markdown")):
        if unquote(anchor).lower() not in {a.lower() for a in anchors_for(dest)}:
            return f"missing anchor: {target}"
    return None


def collect(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
                for f in filenames:
                    if f.lower().endswith((".md", ".markdown")):
                        yield os.path.join(dirpath, f)
        elif os.path.isfile(p):
            yield p
        else:
            print(f"{p}: not found", file=sys.stderr)


def default_root():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def main(argv):
    root, paths = None, []
    it = iter(argv)
    for a in it:
        if a == "--root":
            root = next(it, None)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            paths.append(a)
    if not paths:
        print(__doc__, file=sys.stderr)
        return 2
    root = os.path.abspath(root or default_root())

    problems = files = links = 0
    for path in collect(paths):
        files += 1
        src = os.path.abspath(path)
        for no, line in markdown_lines(src):
            stripped = INLINE_CODE.sub("", line)
            targets = [m.group(1) for m in INLINE.finditer(stripped)]
            d = REF_DEF.match(stripped)
            if d:
                targets.append(d.group(2))
            for t in targets:
                links += 1
                err = check_target(src, t, root)
                if err:
                    problems += 1
                    print(f"{os.path.relpath(src)}:{no}: {err}")
    print(f"-- {files} file(s), {links} link(s), {problems} problem(s)", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Convert a Rigzone raw job-post markdown file into the jobposts JSON skeleton.

Handles ONLY the deterministic, lossless part of the conversion: frontmatter
parsing, slugs, the employment-type/industry lookups, location parsing, meta
dates and a stable uid. Content normalization (title cleanup, description
summarizing, benefits filtering, salary/cert enrichment) is left to the agent,
which refines the emitted JSON afterwards.

Usage:
    python3 md_to_json.py <file.md> [<file2.md> ...]
    python3 md_to_json.py back/data/raw/          # every *.md in the dir

Each input writes back/data/jobposts/job_<uid>.json (relative to the repo root
inferred from the input path) and prints the written path to stdout.
"""

import sys
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

NA = {"", "n/a", "na", "none", "null", "not extracted yet.", "not extracted", "-"}

INDUSTRY_TABLE = [
    (("energy transition", "renewable", "wind", "solar", "adjacent"),
     {"title": "Energy Transition Jobs (O&G-Adjacent)", "slug": "energy-transition"}),
    (("oilfield service", "ofs", "services"),
     {"title": "Oilfield Services Jobs (OFS)", "slug": "oilfield-services"}),
    (("downstream", "refin", "petrochem"),
     {"title": "Downstream Jobs", "slug": "downstream"}),
    (("midstream", "pipeline", "terminal"),
     {"title": "Midstream Jobs", "slug": "midstream"}),
    (("trading", "marketing"),
     {"title": "Trading & Marketing Jobs", "slug": "trading-marketing"}),
    (("offshore",),
     {"title": "Offshore Jobs", "slug": "offshore"}),
    (("upstream", "e&p", "exploration", "production", "drilling", "well"),
     {"title": "Upstream Jobs (E&P)", "slug": "upstream"}),
]
INDUSTRY_FALLBACK = {"title": "Oilfield Services Jobs (OFS)", "slug": "oilfield-services"}


def is_na(v):
    return v is None or str(v).strip().lower() in NA


def slugify(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_frontmatter(raw):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
    if not m:
        raise ValueError("no YAML frontmatter found")
    fm = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        km = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return fm, m.group(2)


def parse_sections(body):
    """Return {heading_lower: raw_block} for each '## Heading' section."""
    sections = {}
    current = None
    buf = []
    for line in body.splitlines():
        hm = re.match(r"^##\s+(.*)$", line)
        if hm:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = hm.group(1).strip().lower()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def bullets(block):
    if not block or is_na(block):
        return []
    out = []
    for line in block.splitlines():
        bm = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bm:
            out.append(bm.group(1).strip())
    if not out:  # prose without bullets -> keep paragraphs as items
        out = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    return [p for p in out if not is_na(p)]


def prose(block):
    if not block:
        return ""
    return re.sub(r"\n\s*\n", "\n\n", block).strip()


# Allowed values mirror back/data/employmentTypeIso.json (the source of truth).
def employment_iso(v):
    s = (v or "").lower()
    if "contract" in s:  # "contractor" and bare "contract" both map here
        return "CONTRACTOR"
    if "intern" in s:
        return "INTERN"
    if "part" in s and "time" in s:
        return "PART_TIME"
    if "temp" in s:
        return "TEMPORARY"
    if "per diem" in s or "per-diem" in s:
        return "PER_DIEM"
    if "volunteer" in s:
        return "VOLUNTEER"
    return "FULL_TIME"


def industry_obj(v):
    s = (v or "").lower()
    for keys, obj in INDUSTRY_TABLE:
        if any(k in s for k in keys):
            return dict(obj)
    return dict(INDUSTRY_FALLBACK)


def parse_location(v):
    if is_na(v):
        return {"city": None, "state": None, "country": None}
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if len(parts) >= 3:
        return {"city": parts[0], "state": ", ".join(parts[1:-1]), "country": parts[-1]}
    if len(parts) == 2:
        return {"city": parts[0], "state": None, "country": parts[1]}
    if len(parts) == 1:
        return {"city": parts[0], "state": None, "country": None}
    return {"city": None, "state": None, "country": None}


def skills_list(v):
    if is_na(v):
        return []
    parts = re.split(r"\s*[,;/&]\s*|\s+and\s+", v)
    return [p.strip() for p in parts if p.strip()]


def clean_list(v):
    if is_na(v):
        return []
    return skills_list(v)


def meta_dates(posted_date, uid):
    created = published = updated = expires = None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(posted_date.strip(), fmt).replace(tzinfo=timezone.utc)
            created = published = dt
            updated = dt
            expires = dt + timedelta(days=90)
            break
        except (ValueError, AttributeError):
            continue

    def iso(d):
        return d.strftime("%Y-%m-%dT00:00:00Z") if d else None

    return {
        "created_at": iso(created),
        "updated_at": iso(updated),
        "published_at": iso(published),
        "expires_at": iso(expires),
        "uid": uid,
        "archived_at": None,
        "is_deleted": False,
    }


def find_repo_root(p):
    p = p.resolve()
    for parent in [p] + list(p.parents):
        if (parent / "back" / "data" / "jobposts").is_dir():
            return parent
    return None


def convert(md_path):
    md_path = Path(md_path)
    raw = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    sections = parse_sections(body)

    id_external = fm.get("id_external", "").strip()
    uid = "job_" + hashlib.sha1(f"rigzone:{id_external}".encode()).hexdigest()[:8]

    source_url = fm.get("source_url", "").split("?")[0]

    description = prose(sections.get("description", "")) or ("" if is_na(fm.get("description")) else fm.get("description"))
    responsibilities = bullets(sections.get("responsibilities", ""))
    qualifications = bullets(sections.get("qualifications", ""))
    benefits = bullets(sections.get("benefits", ""))

    salary = "" if is_na(fm.get("salary")) else fm.get("salary").strip()

    record = {
        "uid": uid,
        "title": fm.get("title", "").strip(),
        "title_slug": fm.get("title_slug", "").strip() or slugify(fm.get("title", "")),
        "description": description,
        "company": "" if is_na(fm.get("company")) else fm.get("company").strip(),
        "company_slug": slugify(fm.get("company", "")),
        "location": "" if is_na(fm.get("location")) else fm.get("location").strip(),
        "location_structure": parse_location(fm.get("location")),
        "skills": skills_list(fm.get("skills")),
        "experience": "" if is_na(fm.get("experience")) else fm.get("experience").strip(),
        "education": "" if is_na(fm.get("education")) else fm.get("education").strip(),
        "employment_type": "" if is_na(fm.get("employment_type")) else fm.get("employment_type").strip(),
        "employment_type_iso": employment_iso(fm.get("employment_type")),
        "is_remote_job": False,
        "posted_date": "" if is_na(fm.get("posted_date")) else fm.get("posted_date").strip(),
        "source_url": source_url,
        "apply_url": None,
        "salary": salary,
        "department": "" if is_na(fm.get("department")) else fm.get("department").strip(),
        "seniority_level": "" if is_na(fm.get("seniority_level")) else fm.get("seniority_level").strip(),
        "certifications": clean_list(fm.get("certifications")),
        "responsibilities": responsibilities,
        "qualifications": qualifications,
        "benefits": benefits,
        "industry": industry_obj(fm.get("industry")),
        "meta": meta_dates(fm.get("posted_date", ""), uid),
    }

    root = find_repo_root(md_path) or md_path.resolve().parents[2]
    out_dir = root / "back" / "data" / "jobposts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{uid}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    targets = []
    for a in argv:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(p.glob("*.md")))
        else:
            targets.append(p)
    if not targets:
        print("no .md files found", file=sys.stderr)
        return 1
    for t in targets:
        if t.name == "pending-posts.md":
            continue
        try:
            out = convert(t)
            print(out)
        except Exception as e:  # noqa: BLE001 - report and continue the batch
            print(f"ERROR {t}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

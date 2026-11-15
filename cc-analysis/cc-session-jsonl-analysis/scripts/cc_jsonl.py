#!/usr/bin/env python3
"""Stream-parse Claude Code session transcripts (.jsonl) without loading them whole.

Subcommands:
  find     [--project DIR | --slug SLUG] [--top N]   list transcripts by size, with their meta descriptions
  extract  <transcript> <out_dir>                    stats.json, rounds, prompts, reports, last texts, timeline
  grep     <transcript> <regex> [--since ISO] [--until ISO] [--roles assistant,user] [--width N]

Run with `python3 -I`. Prints short slices only; never dumps image data.
"""
import argparse
import base64
import collections
import json
import os
import re
import struct
import sys

CACHE_TTL_SECONDS = 300
PNG_MAGIC = b"\x89PNG"


def entries(path):
	with open(path) as handle:
		for number, line in enumerate(handle, 1):
			try:
				yield number, len(line), json.loads(line)
			except json.JSONDecodeError:
				yield number, len(line), {"type": "<unparseable>"}


def message_of(entry):
	message = entry.get("message")
	return message if isinstance(message, dict) else {}


def blocks_of(entry):
	content = message_of(entry).get("content")
	return content if isinstance(content, list) else []


def text_of(entry):
	content = message_of(entry).get("content")
	if isinstance(content, str):
		return content
	return "\n".join(block.get("text", "") for block in blocks_of(entry) if block.get("type") == "text")


def image_size(source):
	data = source.get("data") or ""
	try:
		raw = base64.b64decode(data[:64] + "==")
	except ValueError:
		return None
	if raw[:4] == PNG_MAGIC:
		return struct.unpack(">II", raw[16:24])
	return None


def seconds(a, b):
	from datetime import datetime
	parse = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
	return (parse(b) - parse(a)).total_seconds()


def is_new_instruction(entry):
	"""A user line that starts a round: real text from a person or coordinator, not tool results or harness nudges."""
	if entry.get("type") != "user":
		return False
	origin = entry.get("origin") if isinstance(entry.get("origin"), dict) else {}
	if origin.get("kind") == "coordinator" or "sent a message while you were working" in text_of(entry)[:300]:
		return True
	if entry.get("isMeta"):
		return False
	content = message_of(entry).get("content")
	if isinstance(content, list) and any(block.get("type") in ("tool_result", "image") for block in content):
		return False
	text = text_of(entry).strip()
	if not text or text.startswith("<system-reminder>") or text.startswith("<command-") or text.startswith("<local-command"):
		return False
	if "cut off mid-stream" in text or "handback-send-enforce" in text:
		return False
	return True


def command_find(args):
	if args.project:
		root = args.project
	else:
		slug = args.slug or re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
		root = os.path.expanduser(f"~/.claude/projects/{slug}")
	if not os.path.isdir(root):
		sys.exit(f"no transcript folder: {root}")
	rows = []
	for directory, _, files in os.walk(root):
		for name in files:
			if name.endswith(".jsonl"):
				path = os.path.join(directory, name)
				meta_path = path[:-6] + ".meta.json"
				description = ""
				if os.path.exists(meta_path):
					try:
						description = json.load(open(meta_path)).get("description", "")
					except (OSError, json.JSONDecodeError):
						pass
				kind = "subagent" if "/subagents/" in path else "session"
				rows.append((os.path.getsize(path), kind, description, path))
	rows.sort(reverse=True)
	print(f"{root}\n{len(rows)} transcripts, {sum(r[0] for r in rows) / 2**20:.0f} MB")
	for size, kind, description, path in rows[: args.top]:
		print(f"{size / 2**20:8.1f} MB  {kind:8}  {description[:50]:50}  {path}")


def command_extract(args):
	src, out = args.transcript, args.out_dir
	os.makedirs(out, exist_ok=True)
	meta_path = src[:-6] + ".meta.json"
	meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}

	type_count, type_bytes = collections.Counter(), collections.Counter()
	result_bytes, result_count = collections.Counter(), collections.Counter()
	tool_names = {}
	reads = collections.Counter()
	image_sizes = collections.Counter()
	images_by_place = collections.Counter()
	models = collections.Counter()
	stop_reasons = collections.Counter()
	anomalies, rewrites, timeline, reports, rounds = [], [], [], [], []
	seen_ids = set()
	last_call_ts = None
	current = None
	last_text = ""
	batch_sizes = []

	def open_round(ts, text):
		nonlocal current
		if current is not None:
			current["last_text"] = last_text
		trigger = "first" if not rounds else "notification" if text.lstrip().startswith("<task-notification>") else "coordinator" if "sent a message while you were working" in text[:300] else "user"
		current = dict(index=len(rounds) + 1, trigger=trigger, start=ts, end=ts, prompt=text, calls=0, input=0, cache_read=0, cache_write=0, output=0, max_context=0, tools=collections.Counter(), reads=0)
		rounds.append(current)

	for number, size, entry in entries(src):
		kind = entry.get("type")
		type_count[kind] += 1
		type_bytes[kind] += size
		ts = entry.get("timestamp")
		if kind == "user":
			for block in blocks_of(entry):
				if block.get("type") == "tool_result":
					name = tool_names.get(block.get("tool_use_id"), "?")
					result_bytes[name] += len(json.dumps(block.get("content")))
					result_count[name] += 1
					for item in block.get("content") if isinstance(block.get("content"), list) else []:
						if item.get("type") == "image":
							images_by_place["tool_result"] += 1
							image_sizes[image_size(item.get("source") or {}) or (item.get("source") or {}).get("media_type")] += 1
				elif block.get("type") == "image":
					images_by_place["user_content"] += 1
			if is_new_instruction(entry):
				open_round(ts, text_of(entry))
		if current is None and kind in ("user", "assistant"):
			open_round(ts, text_of(entry) if kind == "user" else "")
		if ts and current is not None:
			current["end"] = ts
		if kind != "assistant":
			continue
		message = message_of(entry)
		usage = message.get("usage") or {}
		if message.get("id") not in seen_ids:
			seen_ids.add(message.get("id"))
			models[message.get("model")] += 1
			stop_reasons[message.get("stop_reason")] += 1
			context = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
			current["calls"] += 1
			current["input"] += usage.get("input_tokens", 0)
			current["cache_read"] += usage.get("cache_read_input_tokens", 0)
			current["cache_write"] += usage.get("cache_creation_input_tokens", 0)
			current["output"] += usage.get("output_tokens", 0)
			current["max_context"] = max(current["max_context"], context)
			gap = seconds(last_call_ts, ts) if (last_call_ts and ts) else 0
			if usage.get("cache_creation_input_tokens", 0) > 0.6 * context > 50_000:
				rewrites.append(dict(ts=ts, tokens=usage.get("cache_creation_input_tokens"), context=context, gap_s=round(gap), after_ttl=gap > CACHE_TTL_SECONDS))
			if message.get("stop_reason") not in ("tool_use", "end_turn") or usage.get("output_tokens", 0) < 50:
				anomalies.append(dict(ts=ts, stop=message.get("stop_reason"), output=usage.get("output_tokens"), model=message.get("model"), text=text_of(entry)[:160]))
			if ts:
				last_call_ts = ts
			batch_sizes.append(0)
		for block in message.get("content") or []:
			if block.get("type") == "text" and block.get("text", "").strip():
				last_text = block["text"]
			if block.get("type") != "tool_use":
				continue
			name, data = block["name"], block.get("input") or {}
			tool_names[block["id"]] = name
			current["tools"][name] += 1
			if name in ("SubagentHandback",):
				reports.append((ts, data.get("message", "")))
			if name == "Read":
				reads[data.get("file_path")] += 1
				current["reads"] += 1
				batch_sizes[-1] += 1
			detail = data.get("file_path") or data.get("command") or data.get("pattern") or data.get("description") or data.get("prompt") or json.dumps(data)
			timeline.append(f"{ts}\tr{current['index']}\t{name}\t{str(detail).replace(chr(10), ' ')[:220]}")
	if current is not None:
		current["last_text"] = last_text

	for index, r in enumerate(rounds, 1):
		open(f"{out}/prompt-{index}.md", "w").write(f"<!-- {r['start']} -->\n{r['prompt']}")
		open(f"{out}/last-text-{index}.md", "w").write(r.get("last_text") or "")
	for index, (ts, text) in enumerate(reports, 1):
		open(f"{out}/report-{index}.md", "w").write(f"<!-- {ts} -->\n{text}")
	open(f"{out}/timeline.tsv", "w").write("\n".join(timeline) + "\n")

	read_batches = collections.Counter(b for b in batch_sizes if b)
	folders = collections.Counter(os.path.dirname(p) for p in reads.elements() if p)
	stats = dict(
		file=src,
		size_mb=round(os.path.getsize(src) / 2**20, 1),
		meta=meta,
		models=dict(models),
		entry_types=dict(type_count),
		entry_mb={k: round(v / 2**20, 1) for k, v in type_bytes.most_common()},
		tool_result_mb={k: round(v / 2**20, 2) for k, v in result_bytes.most_common()},
		tool_result_count=dict(result_count),
		images=dict(images_by_place),
		image_sizes={str(k): v for k, v in image_sizes.most_common(12)},
		reads_total=sum(reads.values()),
		reads_distinct=len(reads),
		reads_repeated={p: n for p, n in reads.most_common() if n > 1},
		read_folders=dict(folders.most_common(25)),
		reads_per_call=dict(sorted(read_batches.items())),
		stop_reasons={str(k): v for k, v in stop_reasons.items()},
		anomalies=anomalies,
		cache_rewrites=rewrites,
		reports=len(reports),
		totals=dict(
			calls=sum(r["calls"] for r in rounds),
			cache_read=sum(r["cache_read"] for r in rounds),
			cache_write=sum(r["cache_write"] for r in rounds),
			output=sum(r["output"] for r in rounds),
			wall_s=round(seconds(rounds[0]["start"], rounds[-1]["end"])) if rounds and rounds[0]["start"] and rounds[-1]["end"] else None,
		),
		rounds=[
			{**{k: v for k, v in r.items() if k not in ("prompt", "last_text", "tools")}, "tools": dict(r["tools"]), "wall_s": round(seconds(r["start"], r["end"])) if r["start"] and r["end"] else None, "prompt_head": r["prompt"][:160]}
			for r in rounds
		],
	)
	json.dump(stats, open(f"{out}/stats.json", "w"), indent=1)

	print(f"{stats['size_mb']} MB  {meta.get('description', '')}  models={stats['models']}")
	print(f"entry MB: {stats['entry_mb']}")
	print(f"images: {stats['images']}  sizes: {stats['image_sizes']}")
	print(f"reads: {stats['reads_total']} ({stats['reads_distinct']} distinct, {len(stats['reads_repeated'])} repeated)  reads per call: {stats['reads_per_call']}")
	print(f"totals: {stats['totals']}")
	print("round  trigger       start                     wall_s  calls  max_ctx  cache_read  cache_write  output  reads  prompt")
	for r in stats["rounds"]:
		print(f"{r['index']:>5}  {r['trigger']:<12}  {r['start']}  {r['wall_s']!s:>6}  {r['calls']:>5}  {r['max_context']:>7}  {r['cache_read']:>10}  {r['cache_write']:>11}  {r['output']:>6}  {r['reads']:>5}  {r['prompt_head'][:60]!r}")
	print(f"cache rewrites: {len(rewrites)}  anomalies: {len(anomalies)}  reports: {len(reports)}")
	for item in rewrites:
		print(f"  rewrite {item}")
	for item in anomalies[:15]:
		print(f"  anomaly {item}")
	print(f"wrote {out}/stats.json, timeline.tsv, prompt-*.md, report-*.md, last-text-*.md")


def command_grep(args):
	pattern = re.compile(args.regex, re.I)
	roles = set(args.roles.split(","))
	for number, _, entry in entries(args.transcript):
		kind = entry.get("type")
		ts = entry.get("timestamp") or ""
		if kind not in roles or (args.since and ts < args.since) or (args.until and ts > args.until):
			continue
		texts = [text_of(entry)]
		if kind == "assistant":
			for block in blocks_of(entry):
				if block.get("type") == "tool_use" and block["name"] in ("SendMessage", "Agent", "Task", "Workflow"):
					texts.append(f"[{block['name']}] " + json.dumps(block.get("input"))[:4000])
		for text in texts:
			for match in pattern.finditer(text):
				start = max(0, match.start() - args.width // 2)
				print(f"{ts}  line {number}  {kind}: …{text[start:start + args.width].replace(chr(10), ' ')}…")
				break


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	sub = parser.add_subparsers(dest="command", required=True)
	find = sub.add_parser("find")
	find.add_argument("--project", help="a ~/.claude/projects/<slug> folder")
	find.add_argument("--slug", help="the project slug (default: derived from the cwd)")
	find.add_argument("--top", type=int, default=25)
	extract = sub.add_parser("extract")
	extract.add_argument("transcript")
	extract.add_argument("out_dir")
	grep = sub.add_parser("grep")
	grep.add_argument("transcript")
	grep.add_argument("regex")
	grep.add_argument("--since")
	grep.add_argument("--until")
	grep.add_argument("--roles", default="assistant,user")
	grep.add_argument("--width", type=int, default=300)
	args = parser.parse_args()
	{"find": command_find, "extract": command_extract, "grep": command_grep}[args.command](args)


if __name__ == "__main__":
	main()

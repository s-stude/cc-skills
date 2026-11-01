#!/usr/bin/env node
// Builds, checks and extracts learn-repo pages made from shared/assets/learn-page.html.
//   build   <file.data.js> <out.html>   put the data into the template, then check it (nothing is written on errors)
//   check   <page.html | file.data.js>  run the checks only
//   extract <page.html> <file.data.js>  write a page's data block to a file so it can be edited and rebuilt
// Exit code 1 on errors. Warnings do not fail.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const TEMPLATE = join(dirname(fileURLToPath(import.meta.url)), "../assets/learn-page.html");
const DATA_START = "// ===== DATA START =====", DATA_END = "// ===== DATA END =====";
const PRESETS_START = "// ===== PRESETS START =====", PRESETS_END = "// ===== PRESETS END =====";
const DATA_NAMES = [ "PAGE", "TYPES", "EDGE_KINDS", "VIEWS", "TOUR", "QUIZ", "GLOSSARY", "SOURCES", "NOTES" ];
const MARKS = [ "code+check", "code", "docs", "inferred" ];
const STATUSES = [ "proposed", "illustrative", "unknown" ];
const CARDS = /^(\?|\*|\d+|\d+\.\.(\d+|\*))$/;
const TEMPLATE_TEXT = /PAGE TITLE|VIEW TITLE|YYYY-MM-DD|FINDINGS|BRANCH|"KIND"|Project · Area/;

function between(text, start, end, what) {
	const a = text.indexOf(start), b = text.indexOf(end);
	if (a < 0 || b < a) throw new Error(`${what} markers not found`);
	return text.slice(a + start.length, b);
}
function evaluate(code, names) {
	return new Function(`${code}\n;return { ${names.join(", ")} };`)();
}

function check(data, presetsCode, html, label) {
	const errors = [], warnings = [], info = [];
	const err = text => errors.push(text), warn = text => warnings.push(text);
	if (/<\/script|<!--/i.test(data)) err("the data contains </script or <!--, which ends the page's script early; split the string, e.g. \"<\\/script\"");
	let D, P;
	try {
		P = evaluate(presetsCode, [ "PRESETS", "PALETTE", "GRID", "SHAPES", "HEADS", "labelChars" ]);
	} catch (error) {
		return { errors: [ `the template's PRESETS block does not evaluate: ${error.message}` ], warnings, info };
	}
	try {
		D = evaluate(data, DATA_NAMES);
	} catch (error) {
		return { errors: [ `the data does not evaluate: ${error.message}. It must declare ${DATA_NAMES.join(", ")} (empty arrays and objects are fine).` ], warnings, info };
	}
	const { PAGE, TYPES, EDGE_KINDS, VIEWS, TOUR, QUIZ, GLOSSARY, SOURCES, NOTES } = D;
	const { PRESETS, GRID, SHAPES, HEADS, labelChars } = P;
	grid = GRID;
	const preset = PRESETS[PAGE?.kind];
	if (!preset) {
		err(`PAGE.kind "${PAGE?.kind}" is not one of ${Object.keys(PRESETS).join(", ")}`);
		return { errors, warnings, info };
	}
	const TYPE = { ...preset.types, ...TYPES }, KIND = { ...preset.edges, ...EDGE_KINDS };
	for (const key of [ "eyebrow", "title", "intro", "sourceNote" ])
		if (!PAGE[key]) err(`PAGE.${key} is empty`);
		else if (TEMPLATE_TEXT.test(PAGE[key])) warn(`PAGE.${key} still holds template text`);
	if (typeof NOTES !== "string") err("NOTES must be a string of HTML (empty when unused)");

	for (const [ name, type ] of Object.entries(TYPES)) {
		if (!SHAPES.includes(type.shape)) err(`TYPES.${name}.shape "${type.shape}" is not one of ${SHAPES.join(", ")}`);
		if (!type.label) err(`TYPES.${name} lacks label`);
		if (!/^#[0-9a-f]{6}$/i.test(type.color ?? "") || !/^#[0-9a-f]{6}$/i.test(type.tint ?? "")) err(`TYPES.${name} needs color and tint as #rrggbb (use PALETTE values)`);
		else {
			if (contrast(type.color, "#ffffff") < 4.5) warn(`TYPES.${name}.color has ${contrast(type.color, "#ffffff").toFixed(1)}:1 against white badge text; needs 4.5`);
			if (contrast(type.tint, "#14142b") < 4.5) warn(`TYPES.${name}.tint has ${contrast(type.tint, "#14142b").toFixed(1)}:1 against the dark label; needs 4.5`);
		}
	}
	for (const [ name, kind ] of Object.entries(EDGE_KINDS)) {
		if (!kind.label || !kind.meaning) err(`EDGE_KINDS.${name} needs label and meaning`);
		for (const end of [ "head", "tail" ]) if (kind[end] && !HEADS.includes(kind[end])) err(`EDGE_KINDS.${name}.${end} "${kind[end]}" is not one of ${HEADS.join(", ")}`);
		if (kind.ends && ![ "none", "text", "crowsfoot" ].includes(kind.ends)) err(`EDGE_KINDS.${name}.ends must be none, text or crowsfoot`);
	}

	if (!Array.isArray(VIEWS) || !VIEWS.length) err("VIEWS is empty");
	const viewIds = new Set();
	const stepX = GRID.cw + GRID.gx, stepY = GRID.ch + GRID.gy;
	const nodeRect = node => { const w = node.w ?? 1, h = node.h ?? 1; return { x: GRID.pad + node.col * stepX, y: GRID.pad + node.row * stepY, w: w * GRID.cw + (w - 1) * GRID.gx, h: h * GRID.ch + (h - 1) * GRID.gy }; };
	const center = rect => ({ x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 });
	const gridPoint = ([ col, row ]) => ({ x: GRID.pad + col * stepX + GRID.cw / 2, y: GRID.pad + row * stepY + GRID.ch / 2 });
	const keyLabels = new Map();

	for (const view of VIEWS ?? []) {
		const at = `view ${view.id ?? "?"}`;
		if (!/^[a-z0-9][a-z0-9-]*$/.test(view.id ?? "")) err(`${at}: id must be lowercase letters, digits and dashes`);
		if (viewIds.has(view.id)) err(`${at}: duplicate view id`);
		viewIds.add(view.id);
		for (const key of [ "title", "purpose", "read" ]) if (!view[key]) err(`${at} lacks ${key}`);
		if (TEMPLATE_TEXT.test(`${view.title} ${view.purpose}`)) warn(`${at} still holds template text`);
		view.nodes ??= []; view.edges ??= []; view.groups ??= [];
		if (!view.nodes.length && !view.gap) err(`${at} has no nodes and no gap; say what is missing instead of leaving it empty`);
		const ids = new Map(), groups = new Map();
		for (const group of view.groups) {
			if (groups.has(group.id)) err(`${at}: duplicate group ${group.id}`);
			groups.set(group.id, group);
			if (!group.label) err(`${at} group ${group.id} lacks label`);
			for (const key of [ "col", "row", "w", "h" ]) if (!Number.isInteger(group[key]) || group[key] < (key === "w" || key === "h" ? 1 : 0)) err(`${at} group ${group.id}: ${key} must be an integer (col/row ≥ 0, w/h ≥ 1)`);
		}
		const depth = group => { let d = 0, current = group; while (current?.parent && d < 6) { current = groups.get(current.parent); d++; } return d; };
		const groupRect = group => { const inset = 8 + depth(group) * 12; return { x: GRID.pad + group.col * stepX - GRID.gx / 2 + inset, y: GRID.pad + group.row * stepY - GRID.gy / 2 + inset, w: group.w * stepX - 2 * inset, h: group.h * stepY - 2 * inset }; };
		for (const group of view.groups) {
			if (group.parent && !groups.has(group.parent)) err(`${at} group ${group.id}: unknown parent group ${group.parent}`);
			if (depth(group) >= 6) err(`${at} group ${group.id}: parent groups form a loop`);
			else if (depth(group) > 1) warn(`${at} group ${group.id} is nested ${depth(group) + 1} deep; the label band gets too thin past 2 levels`);
			if (group.parent && groups.has(group.parent) && !inside(groupRect(group), groupRect(groups.get(group.parent)))) err(`${at} group ${group.id} is not inside its parent group ${group.parent}`);
		}
		for (const node of view.nodes) {
			const nat = `${at} node ${node.id ?? "?"}`;
			if (!node.id) { err(`${nat} lacks id`); continue; }
			if (ids.has(node.id)) err(`${nat}: duplicate id`);
			ids.set(node.id, node);
			if (!TYPE[node.type]) err(`${nat}: unknown type "${node.type}" (known: ${Object.keys(TYPE).join(", ")})`);
			if (!node.label) err(`${nat} lacks label`);
			for (const key of [ "col", "row" ]) if (!Number.isInteger(node[key]) || node[key] < 0) err(`${nat}: ${key} must be an integer ≥ 0`);
			for (const key of [ "w", "h" ]) if (node[key] !== undefined && (!Number.isInteger(node[key]) || node[key] < 1)) err(`${nat}: ${key} must be an integer ≥ 1`);
			markCheck(node, nat, err, warn, VIEWS);
			if (node.group && !groups.has(node.group)) err(`${nat}: unknown group ${node.group}`);
			const key = node.key ?? node.id;
			if (!keyLabels.has(key)) keyLabels.set(key, new Set());
			keyLabels.get(key).add(node.label);
			if (!Number.isInteger(node.col) || !Number.isInteger(node.row)) continue;
			const rect = nodeRect(node), type = TYPE[node.type] ?? {};
			if (node.group && groups.has(node.group) && !inside(rect, groupRect(groups.get(node.group)))) err(`${nat} is not inside its group ${node.group}; widen the group or move the node`);
			for (const group of view.groups) if (group.id !== node.group && !isAncestor(groups, group.id, node.group) && inside(rect, groupRect(group))) warn(`${nat} sits inside boundary ${group.id} but is not a member; set group: "${group.id}" or move it`);
			const fit = textFit(node, type, rect);
			if (fit) warn(`${nat}: ${fit}`);
			const interfaces = [ ...(node.provides ?? []), ...(node.requires ?? []) ];
			if (interfaces.some(name => name.length > 12)) warn(`${nat}: interface names over 12 chars collide in the gap between columns`);
			if (Math.max((node.provides ?? []).length, (node.requires ?? []).length) * 26 + 14 > rect.h) warn(`${nat}: too many interfaces for the box height; set h: 2`);
		}
		const placed = view.nodes.filter(node => Number.isInteger(node.col) && Number.isInteger(node.row));
		for (let i = 0; i < placed.length; i++) for (let j = i + 1; j < placed.length; j++)
			if (overlap(nodeRect(placed[i]), nodeRect(placed[j]), 0)) err(`${at}: nodes ${placed[i].id} and ${placed[j].id} overlap on the grid`);

		const edgeIds = new Set(), labels = [], seen = new Set(), pairs = new Map();
		view.edges.forEach((edge, index) => {
			const key = [ edge.from, edge.to ].sort().join("|");
			if (!pairs.has(key)) pairs.set(key, []);
			pairs.get(key).push(index);
		});
		view.edges.forEach((edge, index) => {
			const id = edge.id ?? `e${index}`;
			const eat = `${at} edge ${id} (${edge.from}→${edge.to})`;
			if (edgeIds.has(id)) err(`${eat}: duplicate edge id`);
			edgeIds.add(id);
			if (!ids.has(edge.from)) err(`${eat}: unknown from node`);
			if (!ids.has(edge.to)) err(`${eat}: unknown to node`);
			const kind = KIND[edge.kind];
			if (!kind) err(`${eat}: unknown kind "${edge.kind}" (known: ${Object.keys(KIND).join(", ")})${edge.kind === "contains" ? ". Containment is a group, not an edge" : ""}`);
			markCheck(edge, eat, err, warn);
			if (!edge.label && kind && kind.head !== "triangle") warn(`${eat} has no label; name the data, call or rule it stands for`);
			if (kind?.ends === "crowsfoot" || kind?.ends === "text") {
				for (const end of [ "fromEnd", "toEnd" ]) {
					if (edge[end] === undefined) (kind.ends === "crowsfoot" ? err : warn)(`${eat} lacks ${end}; use "?" when the count is unknown`);
					else if (!CARDS.test(String(edge[end]))) err(`${eat}: ${end} "${edge[end]}" must look like 1, 0..1, 0..*, 1..* or ?`);
				}
			} else if (edge.fromEnd || edge.toEnd) warn(`${eat}: fromEnd/toEnd are drawn only for kinds with ends; ${edge.kind} has none`);
			for (const point of edge.via ?? []) if (!Array.isArray(point) || point.length !== 2 || point.some(value => typeof value !== "number" || value < -0.5)) err(`${eat}: via points are [col, row] numbers; .5 lands in the gap between cells`);
			const signature = `${edge.from}|${edge.to}|${edge.kind}|${edge.label}`;
			if (seen.has(signature)) warn(`${eat} duplicates another edge`);
			seen.add(signature);
			const from = ids.get(edge.from), to = ids.get(edge.to);
			if (!from || !to || from === to || !Number.isInteger(from.col) || !Number.isInteger(to.col)) return;
			const points = [ center(nodeRect(from)), ...(edge.via ?? []).map(gridPoint), center(nodeRect(to)) ];
			points[0] = exitPoint(nodeRect(from), points[0], points[1]);
			points[points.length - 1] = exitPoint(nodeRect(to), points[points.length - 1], points[points.length - 2]);
			const pair = pairs.get([ edge.from, edge.to ].sort().join("|"));
			const first = [ edge.from, edge.to ].sort()[0];
			for (const node of placed) {
				if (node === from || node === to) continue;
				const rect = nodeRect(node);
				if (points.some((point, i) => i && segmentHits(points[i - 1], point, rect, 4))) warn(`${eat} crosses node ${node.id}; move a node or add via: [[col, row]] to route around it`);
			}
			if (edge.label) {
				let best = 0, length = -1;
				for (let i = 0; i < points.length - 1; i++) { const l = Math.hypot(points[i + 1].x - points[i].x, points[i + 1].y - points[i].y); if (l > length) { length = l; best = i; } }
				const along = pair.length > 1 ? 0.5 + (pair.indexOf(index) - (pair.length - 1) / 2) * (0.36 / (pair.length - 1)) * (edge.from === first ? 1 : -1) : 0.5;
				const mid = { x: points[best].x + (points[best + 1].x - points[best].x) * along, y: points[best].y + (points[best + 1].y - points[best].y) * along };
				const chars = labelChars(points[best], points[best + 1]);
				const lines = wrapCount(edge.label, chars);
				const width = Math.min(edge.label.length, chars) * 6.4 + 12, height = Math.min(lines, 3) * 14 + 6;
				const box = { x: mid.x - width / 2, y: mid.y - height / 2, w: width, h: height };
				if (lines > 3) warn(`${eat}: label wraps past 3 lines and is cut; move the rest into detail`);
				for (const node of placed) if (overlap(box, nodeRect(node), 2)) warn(`${eat}: label sits on node ${node.id}; spread the nodes apart or add via`);
				for (const other of labels) if (overlap(box, other.box, 0)) warn(`${eat}: label overlaps the label of ${other.id}; add via to one of them or shorten`);
				labels.push({ id, box });
			}
		});
		for (const group of view.groups) for (const node of placed) if (!node.group && !isAncestor(groups, group.id, node.group) && overlap(nodeRect(node), groupRect(group), 0) && !inside(nodeRect(node), groupRect(group))) warn(`${at} node ${node.id} straddles the border of group ${group.id}`);
		view._ids = ids;
	}
	for (const view of VIEWS ?? []) {
		if (view.parent && !viewIds.has(view.parent)) err(`view ${view.id}: unknown parent view ${view.parent}`);
		if (view.focus) {
			const parent = VIEWS.find(other => other.id === view.parent);
			if (!view.parent) err(`view ${view.id}: focus needs a parent view`);
			else if (parent && !parent.nodes.some(node => (node.key ?? node.id) === view.focus)) err(`view ${view.id}: focus "${view.focus}" is not a node key in parent view ${view.parent}`);
		}
	}
	for (const view of VIEWS ?? []) for (const node of view.nodes) {
		if (node.detail || node.short) continue;
		if (!VIEWS.some(other => other.nodes.some(twin => (twin.key ?? twin.id) === (node.key ?? node.id) && (twin.detail || twin.short)))) warn(`view ${view.id} node ${node.id} has neither short nor detail here or in another view; its popup says nothing`);
	}
	for (const [ key, names ] of keyLabels) if (names.size > 1) warn(`key ${key} has different labels across views (${[ ...names ].join(" / ")}); keep one name or give the nodes different keys`);

	(TOUR ?? []).forEach((step, index) => {
		const at = `TOUR[${index}]`;
		const view = VIEWS.find(other => other.id === step.view);
		if (!view) { err(`${at}: unknown view ${step.view}`); return; }
		if (!step.text) err(`${at} lacks text`);
		for (const id of step.nodes ?? []) if (!view._ids.has(id)) err(`${at}: unknown node ${id} in view ${view.id}`);
		const edgeIds = new Set(view.edges.map((edge, i) => edge.id ?? `e${i}`));
		for (const id of step.edges ?? []) if (!edgeIds.has(id)) err(`${at}: unknown edge ${id} in view ${view.id}; give the edge an id`);
	});
	(QUIZ ?? []).forEach((item, index) => { if (!item.q || !item.a) err(`QUIZ[${index}] needs q and a`); });
	(GLOSSARY ?? []).forEach((item, index) => { if (!Array.isArray(item) || item.length !== 2) err(`GLOSSARY[${index}] must be [term, meaning]`); });
	(SOURCES ?? []).forEach((item, index) => { if (!item.label) err(`SOURCES[${index}] lacks label`); });

	const rules = KIND_RULES[PAGE.kind];
	if (rules) rules({ VIEWS, TYPE, KIND, custom: new Set(Object.keys(TYPES)), err, warn, info });

	const nodes = VIEWS.reduce((sum, view) => sum + view.nodes.length, 0), edges = VIEWS.reduce((sum, view) => sum + view.edges.length, 0);
	const marks = {};
	for (const view of VIEWS) for (const item of [ ...view.nodes, ...view.edges ]) marks[item.ev ?? "none"] = (marks[item.ev ?? "none"] ?? 0) + 1;
	info.unshift(`${label}: kind ${PAGE.kind}, ${VIEWS.length} views in ${new Set(VIEWS.map(view => view.tab ?? view.title)).size} tabs, ${nodes} nodes, ${edges} edges, ${TOUR.length} tour steps, ${QUIZ.length} questions`);
	info.splice(1, 0, `evidence marks: ${Object.entries(marks).map(([ mark, count ]) => `${mark}=${count}`).join(" ")}`);
	return { errors, warnings, info };
}

function markCheck(item, at, err, warn, views) {
	if (!item.ev) warn(`${at} has no evidence mark (ev)`);
	else if (!MARKS.includes(item.ev)) err(`${at}: ev "${item.ev}" must be one of ${MARKS.join(", ")}`);
	if (item.status && !STATUSES.includes(item.status)) err(`${at}: status "${item.status}" must be one of ${STATUSES.join(", ")}`);
	if (item.refs !== undefined && (!Array.isArray(item.refs) || item.refs.some(ref => typeof ref !== "string"))) err(`${at}: refs must be an array of strings`);
	const twinRefs = views && views.some(view => (view.nodes ?? []).some(node => (node.key ?? node.id) === (item.key ?? item.id) && node.refs?.length));
	if ((item.ev === "code" || item.ev === "code+check") && !item.refs?.length && !twinRefs) warn(`${at} is marked ${item.ev} but has no refs; add file:line or symbol`);
	if (item.status === "illustrative" && item.ev && item.ev !== "inferred" && item.ev !== "docs") warn(`${at} is illustrative but marked ${item.ev}; an invented example is not evidence from code`);
}
function textFit(node, type, rect) {
	const charW = 7.6;
	if (type.shape === "class" || type.shape === "component") {
		const head = 8 + ((node.stereotype ?? type.stereotype ?? type.shape === "component") ? 14 : 0) + wrapCount(node.label, Math.floor((rect.w - 40) / charW)) * 17 + (node.sub ? 14 : 0) + 5;
		const rows = (node.members ?? []).length + (node.ops ?? []).length;
		const blocks = ((node.members ?? []).length ? 1 : 0) + ((node.ops ?? []).length ? 1 : 0);
		const need = head + rows * 15 + blocks * 7 + 4;
		if (rows && need > rect.h) return `${rows} members need about ${Math.ceil(need)}px but the box is ${rect.h}px; set h: ${Math.ceil((need + grid.gy) / (grid.ch + grid.gy))} or trim members`;
		const max = Math.floor((rect.w - 20) / 6.9);
		const long = [ ...(node.members ?? []), ...(node.ops ?? []) ].find(member => member.length > max);
		if (long) return `member "${long}" is longer than ${max} chars and is cut; widen with w: 2 or shorten`;
		return null;
	}
	const innerW = type.shape === "store" ? rect.w - 30 : type.shape === "hex" ? rect.w - 24 : type.shape === "ellipse" ? rect.w * 0.76 : rect.w;
	const labelLines = wrapCount(node.label, Math.floor((innerW - 24) / charW));
	if (labelLines > 2) return `label wraps to ${labelLines} lines and is cut at 2; shorten it or set w: 2`;
	const room = rect.h - 16 - labelLines * 17 - (node.sub ? 14 : 0);
	if (node.sub && node.sub.length > Math.floor((innerW - 20) / 6.2)) return `sub "${node.sub}" is cut at one line; shorten it`;
	const shortLines = node.short ? wrapCount(node.short, Math.floor((innerW - 20) / 6.6)) : 0;
	if (shortLines * 15 > room) return `short text needs ${shortLines} lines but only ${Math.max(0, Math.floor(room / 15))} fit; shorten it, move it to detail, or set w/h`;
	return null;
}
let grid;
function wrapCount(text, max) {
	let lines = 0, line = 0;
	for (let word of String(text ?? "").split(/\s+/).filter(Boolean)) {
		while (word.length > max) { if (line) { lines++; line = 0; } lines++; word = word.slice(max - 1); }
		if (!line) line = word.length;
		else if (line + 1 + word.length <= max) line += 1 + word.length;
		else { lines++; line = word.length; }
	}
	return lines + (line ? 1 : 0);
}
function exitPoint(rect, from, toward) {
	const dx = toward.x - from.x, dy = toward.y - from.y;
	let t = Infinity;
	if (dx > 0) t = Math.min(t, (rect.x + rect.w - from.x) / dx);
	if (dx < 0) t = Math.min(t, (rect.x - from.x) / dx);
	if (dy > 0) t = Math.min(t, (rect.y + rect.h - from.y) / dy);
	if (dy < 0) t = Math.min(t, (rect.y - from.y) / dy);
	if (!Number.isFinite(t)) t = 0;
	return { x: from.x + dx * t, y: from.y + dy * t };
}
function inside(a, b) { return a.x >= b.x - 0.5 && a.y >= b.y - 0.5 && a.x + a.w <= b.x + b.w + 0.5 && a.y + a.h <= b.y + b.h + 0.5; }
function overlap(a, b, margin) { return a.x < b.x + b.w + margin && b.x < a.x + a.w + margin && a.y < b.y + b.h + margin && b.y < a.y + a.h + margin; }
function isAncestor(groups, maybeAncestor, groupId) {
	let current = groups.get(groupId), steps = 0;
	while (current && steps++ < 6) { if (current.id === maybeAncestor) return true; current = groups.get(current.parent); }
	return false;
}
function segmentHits(p, q, rect, shrink) {
	const x0 = rect.x + shrink, y0 = rect.y + shrink, x1 = rect.x + rect.w - shrink, y1 = rect.y + rect.h - shrink;
	let t0 = 0, t1 = 1;
	const dx = q.x - p.x, dy = q.y - p.y;
	for (const [ pp, qq ] of [ [ -dx, p.x - x0 ], [ dx, x1 - p.x ], [ -dy, p.y - y0 ], [ dy, y1 - p.y ] ]) {
		if (pp === 0) { if (qq < 0) return false; continue; }
		const t = qq / pp;
		if (pp < 0) { if (t > t1) return false; if (t > t0) t0 = t; }
		else { if (t < t0) return false; if (t < t1) t1 = t; }
	}
	return t0 < t1;
}
function luminance(hex) {
	const [ r, g, b ] = [ 1, 3, 5 ].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) { const [ x, y ] = [ luminance(a), luminance(b) ].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); }

function cycles(view) {
	const out = new Map(view.nodes.map(node => [ node.id, [] ]));
	for (const edge of view.edges) out.get(edge.from)?.push(edge.to);
	let index = 0;
	const stack = [], on = new Set(), idx = new Map(), low = new Map(), groups = [];
	const visit = v => {
		idx.set(v, index); low.set(v, index); index++; stack.push(v); on.add(v);
		for (const w of out.get(v) ?? []) {
			if (!idx.has(w)) { visit(w); low.set(v, Math.min(low.get(v), low.get(w))); }
			else if (on.has(w)) low.set(v, Math.min(low.get(v), idx.get(w)));
		}
		if (low.get(v) === idx.get(v)) {
			const group = [];
			let w;
			do { w = stack.pop(); on.delete(w); group.push(w); } while (w !== v);
			if (group.length > 1 || (out.get(v) ?? []).includes(v)) groups.push(group.reverse());
		}
	};
	for (const node of view.nodes) if (!idx.has(node.id)) visit(node.id);
	return groups;
}

const KIND_RULES = {
	"c4"({ VIEWS, TYPE, custom, err, warn }) {
		const levels = [ "L1", "L2", "L3", "L4", "UML" ];
		const allowed = {
			L1: [ "person", "system", "external-system" ],
			L2: [ "person", "system", "external-system", "container", "database" ],
			L3: [ "person", "external-system", "container", "database", "component" ],
			L4: [ "component", "code", "external-code", "database", "container" ],
			UML: [ "uml-component", "uml-interface", "external-system", "external-code", "person" ]
		};
		const umlKinds = [ "dependency", "realization", "assembly", "delegation" ];
		for (const view of VIEWS) {
			const at = `view ${view.id}`;
			if (!levels.includes(view.level)) { err(`${at}: level must be one of ${levels.join(", ")}`); continue; }
			for (const node of view.nodes) if (TYPE[node.type] && !allowed[view.level].includes(node.type) && !custom.has(node.type)) warn(`${at}: a ${node.type} node (${node.id}) does not belong at ${view.level}; C4 ${view.level} shows ${allowed[view.level].join(", ")}`);
			for (const edge of view.edges) {
				if (view.level === "UML" && !umlKinds.includes(edge.kind)) warn(`${at}: edge kind ${edge.kind} is not UML component notation; use ${umlKinds.join(", ")}`);
				if (view.level !== "UML" && umlKinds.includes(edge.kind)) warn(`${at}: UML edge kind ${edge.kind} in a C4 view; use uses, async or code-dep`);
			}
			if (view.level === "L1" && view.nodes.length && view.nodes.filter(node => node.type === "system").length !== 1) warn(`${at}: an L1 view shows exactly one focal software system (type system); others are external-system`);
			const parentLevel = { L3: "L2", L4: "L3" }[view.level];
			if (parentLevel && view.nodes.length) {
				const parent = VIEWS.find(other => other.id === view.parent);
				if (!parent) warn(`${at}: an ${view.level} view needs parent (the ${parentLevel} view it zooms into) and focus (the element it expands)`);
				else {
					if (parent.level !== parentLevel) warn(`${at}: parent ${parent.id} is ${parent.level}, expected ${parentLevel}`);
					if (!view.focus) warn(`${at}: set focus to the key of the ${view.level === "L3" ? "container" : "component"} this view expands`);
					const focal = parent.nodes.find(node => (node.key ?? node.id) === view.focus);
					const want = view.level === "L3" ? [ "container", "database" ] : [ "component" ];
					if (focal && !want.includes(focal.type)) warn(`${at}: focus ${view.focus} is a ${focal.type} in ${parent.id}; an ${view.level} view expands a ${want.join(" or ")}`);
				}
			}
		}
		if (!VIEWS.some(view => view.level === "UML")) warn("no UML view; the skill's default is L1–L4 plus a UML component view (keep the view with a gap if detail is missing)");
		for (const level of [ "L1", "L2", "L3", "L4" ]) if (!VIEWS.some(view => view.level === level)) warn(`no ${level} view; keep the level with a gap if the findings do not cover it`);
	},
	"data-flow"({ VIEWS, err, warn, info }) {
		const notations = [ "dfd", "lineage", "pipeline" ];
		for (const notation of notations) if (!VIEWS.some(view => view.notation === notation)) warn(`no ${notation} view; the default is all three (keep the view with a gap if the findings do not support it)`);
		for (const view of VIEWS) {
			const at = `view ${view.id}`;
			if (!notations.includes(view.notation)) { err(`${at}: notation must be one of ${notations.join(", ")}`); continue; }
			const byId = new Map(view.nodes.map(node => [ node.id, node ]));
			if (view.notation === "dfd") {
				for (const node of view.nodes) if (![ "entity", "process", "store" ].includes(node.type)) warn(`${at}: a DFD uses entity, process and store; ${node.id} is ${node.type}`);
				for (const edge of view.edges) {
					const a = byId.get(edge.from), b = byId.get(edge.to);
					if (a && b && a.type !== "process" && b.type !== "process") err(`${at}: ${edge.from} → ${edge.to} moves data between two non-processes; a DFD needs a process in between (show the gap if it is not known)`);
				}
				for (const node of view.nodes.filter(node => node.type === "process")) {
					if (!view.edges.some(edge => edge.to === node.id)) warn(`${at}: process ${node.id} has no input`);
					if (!view.edges.some(edge => edge.from === node.id)) warn(`${at}: process ${node.id} has no output`);
				}
				if (view.level === "context") {
					if (view.nodes.filter(node => node.type === "process").length !== 1) warn(`${at}: a context DFD shows the system as one process`);
					if (view.nodes.some(node => node.type === "store")) warn(`${at}: a context DFD has no internal stores`);
				}
				const parent = VIEWS.find(other => other.id === view.parent);
				if (parent?.notation === "dfd" && view.nodes.length) {
					const flows = v => {
						const ids = new Map(v.nodes.map(node => [ node.id, node ]));
						const set = new Set();
						for (const edge of v.edges) {
							const a = ids.get(edge.from), b = ids.get(edge.to);
							if (a?.type === "entity") set.add(`${a.key ?? a.id} → system: ${edge.label}`);
							if (b?.type === "entity") set.add(`system → ${b.key ?? b.id}: ${edge.label}`);
						}
						return set;
					};
					const outer = flows(parent), inner = flows(view);
					for (const flow of outer) if (!inner.has(flow)) warn(`${at}: not balanced with ${parent.id}; boundary flow "${flow}" is missing here (same entity key and label expected)`);
					for (const flow of inner) if (!outer.has(flow)) warn(`${at}: not balanced with ${parent.id}; boundary flow "${flow}" does not appear in the parent`);
				}
			}
			if (view.notation === "lineage") {
				const hasJobs = view.nodes.some(node => node.type === "job");
				for (const edge of view.edges) {
					const a = byId.get(edge.from), b = byId.get(edge.to);
					if (hasJobs && a && b && a.type !== "job" && b.type !== "job" && b.type !== "consumer") warn(`${at}: ${edge.from} → ${edge.to} links two datasets directly while the view uses job nodes; put the job in between`);
				}
				for (const group of cycles(view)) {
					if (!view.edges.some(edge => group.includes(edge.from) && group.includes(edge.to) && edge.cycle)) warn(`${at}: cycle ${group.join(" → ")}; lineage can loop, but say why on one of its edges with cycle: "…"`);
					info.push(`${at}: cycle ${group.join(" → ")}`);
				}
			}
			if (view.notation === "pipeline") {
				if (![ "ETL", "ELT", "hybrid" ].includes(view.pipeline)) err(`${at}: set pipeline to ETL, ELT or hybrid (where transformation happens relative to loading into the target)`);
				for (const node of view.nodes.filter(node => node.type === "stage")) {
					const touches = view.edges.filter(edge => (edge.from === node.id || edge.to === node.id) && edge.kind !== "trigger");
					if (!touches.length) warn(`${at}: stage ${node.id} moves no data; is it orchestration only?`);
				}
			}
		}
	},
	"module-dependency"({ VIEWS, err, warn, info }) {
		const graphs = VIEWS.filter(view => view.notation === "graph");
		if (!graphs.length) warn("no view with notation \"graph\"; the module dependency graph is the core view");
		for (const view of VIEWS) {
			const at = `view ${view.id}`;
			if (![ "graph", "internals" ].includes(view.notation)) { err(`${at}: notation must be graph or internals`); continue; }
			if (view.notation === "internals") {
				if (!view.module) err(`${at}: an internals view names the module it opens with module: "<key>"`);
				else if (!graphs.some(graph => graph.nodes.some(node => (node.key ?? node.id) === view.module))) err(`${at}: module "${view.module}" is not a node key in any graph view`);
				if (!view.groups.length && view.nodes.length) warn(`${at}: draw the module boundary as a group so it is clear which parts are inside`);
			}
			for (const group of cycles(view)) info.push(`${at}: cycle ${group.join(" → ")}`);
		}
		const internals = new Set(VIEWS.filter(view => view.notation === "internals").map(view => view.module));
		for (const graph of graphs) for (const node of graph.nodes) if (node.type === "module" && !internals.has(node.key ?? node.id)) info.push(`module ${node.key ?? node.id} has no internals view`);
	},
	"data-model"({ VIEWS, KIND, err, warn }) {
		const levels = [ "conceptual", "logical", "physical" ], notations = [ "concept", "erd", "uml" ];
		for (const level of levels) if (!VIEWS.some(view => view.level === level)) warn(`no ${level} view; keep it with a gap if the findings do not cover it`);
		if (!VIEWS.some(view => view.notation === "uml")) warn("no UML class view");
		if (!VIEWS.some(view => view.notation === "erd")) warn("no ERD view");
		for (const view of VIEWS) {
			const at = `view ${view.id}`;
			if (!levels.includes(view.level)) err(`${at}: level must be one of ${levels.join(", ")}`);
			if (!notations.includes(view.notation)) { err(`${at}: notation must be one of ${notations.join(", ")}`); continue; }
			const erdKinds = [ "erd", "erd-weak" ], umlKinds = [ "association", "navigable", "aggregation", "composition", "generalization", "realization", "dependency" ];
			for (const edge of view.edges) {
				if (view.notation === "erd" && !erdKinds.includes(edge.kind)) warn(`${at}: ERD edges use erd or erd-weak; ${edge.kind} is UML or conceptual`);
				if (view.notation === "uml" && !umlKinds.includes(edge.kind)) warn(`${at}: UML class edges use ${umlKinds.join(", ")}; ${edge.kind} is not one`);
				if (view.notation === "concept" && edge.kind !== "relates") warn(`${at}: conceptual edges use relates`);
				if (KIND[edge.kind]?.ends === "none" && (edge.fromEnd || edge.toEnd)) warn(`${at}: ${edge.kind} has no multiplicities`);
			}
			for (const node of view.nodes) {
				const members = node.members ?? [];
				if (view.level === "conceptual" && members.some(member => /\b(PK|FK)\b|varchar|int\b|ObjectId/i.test(member))) warn(`${at}: ${node.id} shows keys or storage types in a conceptual view`);
				if (view.level === "physical" && view.notation === "erd" && members.some(member => /\bFK\b/.test(member)) && !view.edges.some(edge => edge.from === node.id || edge.to === node.id)) warn(`${at}: ${node.id} has FK members but no relationship drawn`);
				if (view.notation === "uml" && (node.ops ?? []).length && node.ev !== "code" && node.ev !== "code+check") warn(`${at}: ${node.id} lists operations without a code mark; add operations only when the code has them`);
			}
		}
	}
};

function report(result) {
	for (const line of result.info) console.log(line);
	for (const line of result.warnings) console.log("warn:", line);
	for (const line of result.errors) console.log("error:", line);
	console.log(`${result.errors.length} error(s), ${result.warnings.length} warning(s)`);
}
function presetsOf(text) { return between(text, PRESETS_START, PRESETS_END, "PRESETS START / PRESETS END"); }

const [ command, input, output ] = process.argv.slice(2);
const usage = "usage: page.mjs build <file.data.js> <out.html> | check <page.html|file.data.js> | extract <page.html> <file.data.js>";
try {
	if (command === "build" && input && output) {
		const template = readFileSync(TEMPLATE, "utf8");
		const data = readFileSync(input, "utf8");
		const presets = presetsOf(template);
		const start = template.indexOf(DATA_START), end = template.indexOf(DATA_END);
		const html = `${template.slice(0, start + DATA_START.length)}\n${data.trim()}\n${template.slice(end)}`;
		const result = check(data, presets, null, input);
		report(result);
		if (result.errors.length) { console.log(`not written: fix the errors in ${input}`); process.exit(1); }
		mkdirSync(dirname(resolve(output)), { recursive: true });
		writeFileSync(output, html);
		console.log(`written: ${output}`);
	} else if (command === "check" && input) {
		const text = readFileSync(input, "utf8");
		const isHtml = text.includes(DATA_START);
		const presets = presetsOf(isHtml ? text : readFileSync(TEMPLATE, "utf8"));
		const result = check(isHtml ? between(text, DATA_START, DATA_END, "DATA START / DATA END") : text, presets, isHtml ? text : null, input);
		report(result);
		process.exit(result.errors.length ? 1 : 0);
	} else if (command === "extract" && input && output) {
		const data = between(readFileSync(input, "utf8"), DATA_START, DATA_END, "DATA START / DATA END");
		mkdirSync(dirname(resolve(output)), { recursive: true });
		writeFileSync(output, data.trim() + "\n");
		console.log(`written: ${output}`);
	} else {
		console.error(usage);
		process.exit(2);
	}
} catch (error) {
	console.error("error:", error.message);
	process.exit(1);
}

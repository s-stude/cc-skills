#!/usr/bin/env node
// Validates the DATA block of a flow diagram built from assets/flow-template.html.
// Usage: node check-flow.mjs <path/to/diagram.html>
// Exit code 1 on errors. Warnings do not fail the check.
import { readFileSync } from "node:fs";

const file = process.argv[2];
if (!file) {
	console.error("usage: check-flow.mjs <diagram.html>");
	process.exit(2);
}
const html = readFileSync(file, "utf8");
const start = html.indexOf("// ===== DATA START =====");
const end = html.indexOf("// ===== DATA END =====");
if (start < 0 || end < 0) {
	console.error("error: DATA START / DATA END markers not found. Keep them around the data block.");
	process.exit(1);
}
const block = html.slice(start, end);
let data;
try {
	data = new Function(`${block}; return { PAGE, LANES, TAGS, STEPS, SCENARIOS };`)();
} catch (error) {
	console.error("error: the data block does not evaluate:", error.message);
	process.exit(1);
}
const { PAGE, LANES, TAGS, STEPS, SCENARIOS } = data;
const errors = [], warnings = [];
const err = text => errors.push(text), warn = text => warnings.push(text);

const laneIds = new Set(LANES.map(lane => lane.id));
if (LANES.length < 3 || LANES.length > 8) warn(`${LANES.length} lanes; 4 to 8 reads best`);
for (const lane of LANES) {
	for (const key of [ "id", "name", "sub", "color", "tint" ])
		if (!lane[key]) err(`lane ${lane.id ?? "?"} lacks ${key}`);
	if ((lane.sub ?? "").length > 34) warn(`lane ${lane.id} sub is ${lane.sub.length} chars; over ~34 it wraps to two lines, over ~70 it is cut`);
	if ((lane.name ?? "").length > 24) warn(`lane ${lane.id} name is ${lane.name.length} chars; the header pill fits about 24`);
}

const seen = new Set();
STEPS.forEach((step, index) => {
	const label = `step ${step.n}`;
	if (step.n !== index + 1) err(`${label} is at position ${index + 1}; number steps 1..N in order`);
	if (seen.has(step.n)) err(`${label} is duplicated`);
	seen.add(step.n);
	if (!laneIds.has(step.lane)) err(`${label} uses unknown lane "${step.lane}"`);
	for (const key of [ "title", "box", "detail" ])
		if (!step[key]) err(`${label} lacks ${key}`);
	if (!step.refs?.length) warn(`${label} has no refs; the reader cannot check it`);
	if (!step.ev) warn(`${label} has no evidence mark (ev)`);
	else if (![ "✓", "code", "docs", "inferred" ].includes(step.ev)) warn(`${label} has an unusual ev "${step.ev}"`);
	if (step.tag && !TAGS[step.tag]) err(`${label} uses unknown tag "${step.tag}"`);
	if ((step.title ?? "").length > 44) warn(`${label} title is ${step.title.length} chars; over ~40 it wraps to three lines`);
	for (const word of (step.title ?? "").split(/\s+/)) if (word.length > 18) warn(`${label} title word "${word}" is ${word.length} chars; it will break mid-word next to the badge`);
	if ((step.loopLabel ?? "").length > 48) warn(`${label} loopLabel is ${step.loopLabel.length} chars; it runs past a short loop`);
	if ((step.box ?? "").length > 100) warn(`${label} box text is ${step.box.length} chars; keep the box for the concrete what, move the rest to detail`);
	if ((step.branch ?? "").length > 160) warn(`${label} branch text is ${step.branch.length} chars; it will dominate the box`);
	if ((step.detail ?? "").split(/[.!?]\s/).length > 7) warn(`${label} detail is long; the panel scrolls after ~5 sentences`);
	for (const side of step.also ?? []) {
		if (!laneIds.has(side.lane)) err(`${label} side effect uses unknown lane "${side.lane}"`);
		if (side.lane === step.lane) err(`${label} side effect points at its own lane; use the box or detail instead`);
		if (![ "to", "from", "both" ].includes(side.dir)) err(`${label} side effect dir must be to|from|both`);
	}
	if (step.loopTo !== undefined) {
		if (!STEPS.some(other => other.n === step.loopTo)) err(`${label} loops to missing step ${step.loopTo}`);
		else if (step.loopTo >= step.n) warn(`${label} loops forward to ${step.loopTo}; loops are drawn for jumps back`);
	}
});
const loopCount = STEPS.filter(step => step.loopTo !== undefined).length;
if (loopCount > 2) warn(`${loopCount} loops; more than two crowd the left margin, keep the reruns a reader can trigger and move the rest to branch text`);
if (STEPS.length < 8) warn(`${STEPS.length} steps; under ~10 a list may serve better than a map`);
if (STEPS.length > 32) warn(`${STEPS.length} steps; over ~30 split the flow into two diagrams`);

const stepNumbers = new Set(STEPS.map(step => step.n));
if (!SCENARIOS.length || SCENARIOS[0].steps.length !== STEPS.length) warn("the first scenario should be \"All steps\" with every step");
for (const scenario of SCENARIOS) {
	for (const n of scenario.steps) if (!stepNumbers.has(n)) err(`scenario ${scenario.id} lists missing step ${n}`);
	for (const n of Object.keys(scenario.notes ?? {})) if (!stepNumbers.has(Number(n))) err(`scenario ${scenario.id} notes missing step ${n}`);
	if (scenario !== SCENARIOS[0] && !scenario.summary) warn(`scenario ${scenario.id} has no summary`);
}
for (const key of [ "eyebrow", "title", "intro", "sourceNote" ]) if (!PAGE[key] || /FLOW TITLE|Product · Area|YYYY-MM-DD/.test(PAGE[key])) warn(`PAGE.${key} still holds template text`);
if (/example\.request|Database table|A constraint the diagram cannot show/.test(html)) warn("the CARDS or LIMITS sections still hold template text");

const perLane = Object.fromEntries(LANES.map(lane => [ lane.id, STEPS.filter(step => step.lane === lane.id).length ]));
const sideLanes = new Set(STEPS.flatMap(step => (step.also ?? []).map(side => side.lane)));
for (const [ id, count ] of Object.entries(perLane)) if (!count && !sideLanes.has(id)) warn(`lane ${id} has neither a step nor a side effect; drop it`);

console.log(`${file}: ${LANES.length} lanes, ${STEPS.length} steps, ${SCENARIOS.length} scenarios, ${STEPS.filter(s => s.tag).length} tagged, ${STEPS.filter(s => (s.also ?? []).length).length} with side effects`);
console.log("steps per lane:", Object.entries(perLane).map(([ id, count ]) => `${id}=${count}`).join(" "));
for (const text of warnings) console.log("warn:", text);
for (const text of errors) console.log("error:", text);
process.exit(errors.length ? 1 : 0);

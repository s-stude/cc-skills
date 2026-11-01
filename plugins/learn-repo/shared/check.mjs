#!/usr/bin/env node
// Self-test for the plugin: rebuilds every example page from shared/examples/<kind>.data.js and fails on
// check errors, check warnings, or an example page that is stale against the template.
//   node shared/check.mjs          rebuild the example pages, then check
//   node shared/check.mjs --check  check only (for CI or before committing)
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const shared = dirname(fileURLToPath(import.meta.url));
const page = join(shared, "scripts/page.mjs");
const template = readFileSync(join(shared, "assets/learn-page.html"), "utf8");
const START = "// ===== DATA START =====", END = "// ===== DATA END =====";
const checkOnly = process.argv.includes("--check");
const problems = [];

for (const kind of [ "c4", "data-flow", "data-model", "module-dependency" ]) {
	const data = join(shared, "examples", `${kind}.data.js`), out = join(shared, "examples", `${kind}.html`);
	const expected = `${template.slice(0, template.indexOf(START) + START.length)}\n${readFileSync(data, "utf8").trim()}\n${template.slice(template.indexOf(END))}`;
	if (!checkOnly) writeFileSync(out, expected);
	else if (readFileSync(out, "utf8") !== expected) problems.push(`${kind}: examples/${kind}.html is stale; run node shared/check.mjs`);
	try {
		const result = execFileSync("node", [ page, "check", out ], { encoding: "utf8" });
		const warnings = result.split("\n").filter(line => line.startsWith("warn:"));
		if (warnings.length) problems.push(`${kind}: ${warnings.length} warning(s)\n  ${warnings.join("\n  ")}`);
	} catch (error) {
		problems.push(`${kind}: check failed\n${error.stdout ?? error.message}`);
	}
	console.log(`${checkOnly ? "checked" : "built and checked"}: ${kind}`);
}
for (const text of problems) console.log("problem:", text);
process.exit(problems.length ? 1 : 0);

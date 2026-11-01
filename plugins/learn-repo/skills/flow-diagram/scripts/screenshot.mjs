#!/usr/bin/env node
// Full-page screenshot of a diagram with headless Chromium, for the render check when no browser tool is at hand.
// Usage: node screenshot.mjs <url-or-path.html> <out.png> [width]
// Needs the playwright package reachable from the current directory (npm i -D playwright && npx playwright install chromium),
// or PLAYWRIGHT_MODULE pointing at an installed copy. Prints console errors; exits 1 if the page threw.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const [target, out = "diagram.png", width = "1600"] = process.argv.slice(2);
if (!target) {
	console.error("usage: screenshot.mjs <url-or-path.html> <out.png> [width]");
	process.exit(2);
}
let chromium;
try {
	({ chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? "playwright"));
} catch {
	console.error("playwright is not installed here. Run: npm i -D playwright && npx playwright install chromium, or set PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs");
	process.exit(2);
}
const url = /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href;
const browser = await chromium.launch({ headless: true, ...process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {} });
const page = await browser.newPage({ viewport: { width: Number(width), height: 1000 } });
const errors = [];
page.on("console", message => { if (message.type() === "error" && !/favicon/.test(message.text())) errors.push(message.text()); });
page.on("pageerror", error => errors.push(`pageerror: ${error.message}`));
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const height = await page.evaluate(() => document.body.scrollHeight);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log(`${out}: ${width}x${height}, ${errors.length} console error(s)`);
for (const text of errors) console.log("error:", text);
process.exit(errors.length ? 1 : 0);

#!/usr/bin/env node
// Renders a learn page in headless Chromium, screenshots every tab and checks the rendered result.
// Usage: node screenshot.mjs <page.html | url> <out-dir> [width=1440]
// Writes <out-dir>/tab-<n>.png per tab at the given width and narrow-<n>.png at 390 px.
// Checks: console errors, edge labels overlapping boxes or each other, node text spilling out of its box,
// horizontal page overflow at 390 px, and the details popup opening on click and closing on Escape.
// Needs the playwright package: npm i -D playwright && npx playwright install chromium,
// or PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs. Exit code 1 when a check fails.
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [ target, outDir = "tmp/learn-shots", width = "1440" ] = process.argv.slice(2);
if (!target) {
	console.error("usage: screenshot.mjs <page.html|url> <out-dir> [width]");
	process.exit(2);
}
let chromium;
try {
	({ chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? "playwright"));
} catch {
	console.error("playwright is not installed here. Run: npm i -D playwright && npx playwright install chromium, or set PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs");
	process.exit(2);
}
mkdirSync(outDir, { recursive: true });
const url = /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href;
const browser = await chromium.launch({ headless: true, ...process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {} });
const problems = [];

function geometryCheck() {
	const found = [];
	const box = item => item.getBoundingClientRect();
	const hit = (a, b, m = 0) => a.left < b.right - m && b.left < a.right - m && a.top < b.bottom - m && b.top < a.bottom - m;
	for (const panel of document.querySelectorAll(".panel:not([hidden])")) {
		for (const section of panel.querySelectorAll("section[id^='view-']")) {
			const view = section.id.slice(5);
			const frames = [ ...section.querySelectorAll(".node") ].map(node => ({ id: node.dataset.id, rect: box(node.querySelector(".frame")), node }));
			const labels = [ ...section.querySelectorAll(".elabel") ].map(label => ({ id: label.dataset.for, rect: box(label.querySelector("rect")) }));
			for (const label of labels) {
				for (const frame of frames) if (hit(label.rect, frame.rect, 1)) found.push(`${view}: label of edge ${label.id} overlaps box ${frame.id}`);
				for (const other of labels) if (other !== label && other.id > label.id && hit(label.rect, other.rect, 1)) found.push(`${view}: labels of edges ${label.id} and ${other.id} overlap`);
			}
			for (const frame of frames) {
				for (const text of frame.node.querySelectorAll("text:not([data-outside])")) {
					const r = box(text);
					if (r.width && (r.left < frame.rect.left - 2 || r.right > frame.rect.right + 2 || r.bottom > frame.rect.bottom + 2)) found.push(`${view}: text "${text.textContent.slice(0, 30)}" spills out of box ${frame.id}`);
				}
			}
		}
	}
	return found;
}

for (const [ name, viewport ] of [ [ "tab", { width: Number(width), height: 1000 } ], [ "narrow", { width: 390, height: 844 } ] ]) {
	const page = await browser.newPage({ viewport });
	const errors = [];
	page.on("console", message => { if (message.type() === "error" && !/favicon/.test(message.text())) errors.push(message.text()); });
	page.on("pageerror", error => errors.push(`pageerror: ${error.message}`));
	await page.goto(url, { waitUntil: "networkidle" });
	await page.waitForTimeout(500);
	const tabs = await page.locator(".tab").count();
	for (let i = 0; i < tabs; i++) {
		await page.locator(".tab").nth(i).click();
		await page.waitForTimeout(250);
		const label = await page.locator(".tab").nth(i).textContent();
		if (name === "tab") for (const issue of await page.evaluate(geometryCheck)) problems.push(`tab "${label}": ${issue}`);
		else {
			const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
			if (overflow > 1) problems.push(`tab "${label}" at 390 px: page scrolls sideways by ${overflow}px (only diagrams may scroll)`);
		}
		await page.screenshot({ path: join(outDir, `${name}-${i + 1}.png`), fullPage: true });
	}
	if (name === "tab") {
		const node = page.locator(".panel:not([hidden]) .node").first();
		if (await node.count()) {
			await page.locator(".tab").first().click();
			await page.locator(".panel:not([hidden]) .node").first().click();
			if (await page.locator("#detail").isHidden()) problems.push("clicking a box did not open the details popup");
			await page.keyboard.press("Escape");
			if (await page.locator("#detail").isVisible()) problems.push("Escape did not close the details popup");
		}
	}
	for (const text of errors) problems.push(`${name}: console error: ${text}`);
	console.log(`${name}: ${tabs} tab(s) at ${viewport.width}px → ${outDir}/${name}-*.png`);
	await page.close();
}
await browser.close();
for (const text of problems) console.log("problem:", text);
console.log(`${problems.length} problem(s)`);
process.exit(problems.length ? 1 : 0);

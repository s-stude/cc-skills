---
name: flow-diagram
description: Turn finished research about how a process, feature or request flows through a system into an interactive single-file HTML swimlane diagram (Tailwind, light theme, vibrant lane colours) with numbered steps, scenario and layer filters, branch strips, side effects, a clickable detail panel with file references and evidence marks, reference cards and a step list. Use whenever the user asks to visualize, diagram, map or draw a flow, a pipeline, a request path, a lifecycle or "what happens when", asks for a swimlane, a flow map or an HTML diagram from notes, docs or an analysis, or points at research documents and wants them turned into a picture, even if they do not say "diagram". The research must already exist; this skill lays it out, it does not investigate the code.
---

# Visualize with a flow diagram

The output is one HTML file: a swimlane map where each column is a layer of the system and time runs down, every step is a clickable box with a number, a short "what", an amber strip for its stop and fallback cases, side boxes for the calls and records it touches, a detail panel with file references and an evidence mark, scenario chips that fade the steps not on a path, layer chips that focus one column, reference cards under the map, and the same steps as a numbered list. The user has done the research already. This skill turns that research into the page without re-investigating.

Bundled (paths relative to `${CLAUDE_SKILL_DIR}`, this skill's folder):

- `assets/flow-template.html` — the whole page. A data block at the top of the script (`DATA START` … `DATA END`) and two HTML blocks (`CARDS`, `LIMITS`) are the parts that change; the rendering engine below them is generic.
- `references/data-model.md` — every field of the data block, the palette, writing rules and a worked example. Read it before filling the template.
- `scripts/check-flow.mjs` — validates a filled diagram: lane and step references, numbering, missing refs or evidence marks, template text left behind, texts too long for a box.

## 1. Read the research as a flow, not as a document

Read every source the user points at (markdown notes, an architecture section, a business-flow write-up, a spec). While reading, keep five lists. They become the data block.

1. **Layers**: the places the flow passes through, in the order the user meets them: screen, transport, server entry, the module that does the work, external services, storage. Four to eight. Merge layers the research cannot tell apart; split a layer the research describes as two different kinds of work (deterministic rules versus a model, for instance).
2. **Steps**: each observable thing that happens, in order, with the layer it happens in. Twelve to thirty. If the research is a numbered business flow, keep its numbering and order, and split a step only where it crosses a lane. A limit or constraint is not a step; it becomes a branch on the step it constrains or a line in the closing limits list.
3. **Branches**: for every step, what stops, skips or falls back there, with the cause. Research usually scatters these in asides, tables of "degraded outcomes" and "limits" sections. Collect them per step.
4. **Side effects**: calls to other layers, messages sent, rows and files written. Each becomes a side box on the lane it touches.
5. **Scenarios**: the distinct paths the research names: the full run, a run where a cache or rules make stages unnecessary, a dependency down, a stop condition, a retry, another caller reusing the same core. Three to six.

Also note the provenance: which documents, which date and branch or version, the path prefixes they use, and whether the research carries evidence marks. If the research names numbers (batch sizes, timeouts, thresholds) keep the ref next to each; those go into boxes and branches only with a ref.

If something a box needs is missing from the research (which layer a step runs in, what happens on failure), ask the user in one message listing every gap, rather than guessing. A diagram states things with more confidence than prose, so a guess here misleads more than a guess in a document. The same holds for scenario summaries and notes: they say what the source says, and a sentence the source does not support is labelled as an assumption inside the sentence. Counts written as words ("two pushes") are numbers too.

If you do open the code to check a fact, record it: mark those steps `✓`, keep the ref, and say in `sourceNote` which steps were re-read and on what date. A number that only the code gives must not sit on a step marked `docs`.

## 2. Fill the template

Copy `${CLAUDE_SKILL_DIR}/assets/flow-template.html` to where the user wants it, next to the research documents by default, and name it after the flow (`<topic>-flow.html`). Then replace the data block and the two HTML blocks; read `references/data-model.md` for the fields and the palette.

Order of work that avoids rework:

1. `LANES` first. Pick the colours from the palette in the reference; keep red for the lane whose use costs money or leaves the system.
2. `STEPS` next, in one pass, with `title`, `lane`, `box`, `detail`, `refs`, `ev`. Then a second pass adding `branch`, `via`, `also`, `tag`, `loopTo`.
3. `SCENARIOS`, built with `without(ALL, [ … ])` so a later renumbering fails loudly in the check instead of silently fading the wrong boxes. Write `notes` for the steps that behave differently on each path, including skipped ones.
4. `PAGE`: eyebrow, title as a "what happens when" sentence, intro, and a `sourceNote` naming the sources, date, branch, path prefixes and the evidence legend.
5. `CARDS`: two to four. The usual set is the messages between the parties, the external calls per run and when each is skipped, the data structure that crosses the module boundary, and who else calls the same core. `LIMITS`: the constraints a box cannot show. Delete the section if there are none.

Rules of thumb that keep the map readable:

- A box says the concrete what in under 90 characters; everything else is detail. The check script warns when a text will wrap into a tall box.
- `via` goes on every arrow that crosses a lane boundary and carries a named message or call.
- Side boxes are for things another lane can observe. Internal bookkeeping is detail text.
- Loops are for a rerun or retry the user can trigger; draw at most one or two, and say on the label what differs on the second pass. A retry job or an internal re-queue is branch text, not a loop.
- Lane subtitles fit about 34 characters and titles about 40; a single identifier longer than about 18 characters breaks mid-word, so identifiers go in the box or the refs. The check script warns on all three.
- Evidence marks are a promise, not decoration. Carry over the marks the research gives. Where the research has none, mark `docs`; mark `✓` only for a code path this session has actually read.

## 3. Check the data

```bash
node ${CLAUDE_SKILL_DIR}/scripts/check-flow.mjs <path/to/diagram.html>
```

Errors (unknown lane, step out of order, scenario pointing at a missing step, unknown tag) must be fixed. Warnings are judgement calls; most mean a text is too long for its box or a step lacks a ref or an evidence mark. Template text left in `PAGE`, `CARDS` or `LIMITS` is flagged too.

## 4. Look at it in a browser

The page loads Tailwind and fonts from CDNs and renders the SVG with JavaScript, so a text check is not enough. Serve the folder and open the page with whatever browser tool the session has (a Playwright or Chrome MCP, or the user's browser). `file://` URLs are usually blocked by browser tools; a local server is not:

```bash
cd <folder-with-the-html> && python3 -m http.server 8911 --bind 127.0.0.1
```

Pick a free port; if a screenshot shows someone else's page, the port was taken. When no browser tool is available, or another session holds the Playwright browser, `node ${CLAUDE_SKILL_DIR}/scripts/screenshot.mjs <url> <out.png>` takes the full-page screenshot with headless Chromium and prints console errors (it needs the `playwright` package; the header of the script says how). Then, in the browser or on the screenshot:

1. Read the console. The only expected messages are the Tailwind CDN production notice and a favicon 404. Anything else is a bug in the data block, usually a missing comma or an unescaped quote.
2. Take a full-page screenshot at about 1600 px wide and look at it in slices (crop it with PIL if the page is tall). Check that lane subtitles are not cut, that titles do not run under a tag badge, that side boxes do not overlap each other or cross a box, that branch strips are not taller than the box above them, that loop lines and labels do not overlap each other or the left edge, and that the lane headers stay pinned while scrolling. These are the defects the first test runs produced; the check script's warnings predict most of them.
3. Click a scenario chip and a step box. The faded steps should match the scenario's `steps`, the note should appear in the panel, and the panel should list the refs.

Fix what the screenshot shows, re-run the check script, reload. Stop the local server when done.

## 5. Hand it over

Link the diagram from the research documents it was built from (a "Related documents" list or a one-line pointer near the top), so the next reader finds it. Then report, in prose: the file path, the lane and step counts, the scenarios, which steps carry which evidence mark and why, and anything the research left open that the diagram therefore does not show. Mention that the page needs network access for Tailwind and the fonts; offer to inline them if the user wants it offline.

## When not to use this layout

- Fewer than about ten steps, or steps that do not cross layers: a numbered list or a sequence of sentences says it better.
- A state machine or a data model: the swimlane map is for one run through time, not for states or entities.
- A dashboard or chart of measurements: that is data visualization, not a flow.

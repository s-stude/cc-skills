# Learn page: data file, build and checks

The four page skills of the learn-repo plugin (`learn-repo:c4-model`, `learn-repo:data-flow`, `learn-repo:module-dependency`, `learn-repo:data-model`) produce the same kind of page from the same template in `<root>/shared/` (`<root>` is the plugin root the SKILL.md gives). The page look, interactions, notation presets, checks and this reference are identical across the four skills. Only `PAGE.kind` and the views differ.

## Contents

1. [Workflow](#workflow)
2. [The data file](#the-data-file)
3. [Views](#views)
4. [Nodes, groups and edges](#nodes-groups-and-edges)
5. [Layout on the grid](#layout-on-the-grid)
6. [Node types and edge kinds per kind](#node-types-and-edge-kinds-per-kind)
7. [Evidence marks and status](#evidence-marks-and-status)
8. [Tour, quiz, glossary, sources, notes](#tour-quiz-glossary-sources-notes)
9. [What the checks catch](#what-the-checks-catch)
10. [Look at it in a browser](#look-at-it-in-a-browser)

## Workflow

You write only a data file. The template holds the page, the styles, the rendering engine and the notation; you never copy or edit it.

```bash
ROOT=<root>
mkdir -p ./tmp/learn
cp $ROOT/shared/examples/<kind>.data.js ./tmp/learn/<name>.data.js         # start from the worked example
# edit ./tmp/learn/<name>.data.js
node $ROOT/shared/scripts/page.mjs build ./tmp/learn/<name>.data.js docs/learn/<name>.html
node $ROOT/shared/scripts/screenshot.mjs docs/learn/<name>.html ./tmp/learn/shots-<name>
```

- `build` checks the data first and writes nothing when there are errors. Fix every error. Warnings are judgement calls; most are real layout or evidence problems, so fix them unless you can say why not.
- To change an existing page, `node $ROOT/shared/scripts/page.mjs extract <page.html> ./tmp/learn/<name>.data.js`, edit, build again.
- `check <page.html | file.data.js>` runs the checks alone.
- `./tmp` is the scratch folder in the project root. The data file stays there; the HTML holds a copy of the data.
- Output: the path the user gives; otherwise `docs/learn/<kind>-<topic>.html` in the project root. If that file exists and was not made from this template, pick another name and say so.
- The page loads Tailwind from its CDN, so it needs network access. Mention that when handing it over.

## The data file

Plain JavaScript that declares exactly these constants. Keep every one of them, even when empty.

```js
const PAGE = { kind, eyebrow, title, intro, sourceNote };
const TYPES = {};        // extra node types, rarely needed
const EDGE_KINDS = {};   // extra edge kinds, rarely needed
const VIEWS = [ … ];
const TOUR = [];
const QUIZ = [];
const GLOSSARY = [];
const SOURCES = [];
const NOTES = "";
```

| PAGE field | What it is |
|---|---|
| `kind` | `c4`, `data-flow`, `module-dependency` or `data-model`. Selects the notation presets and the kind-specific checks. |
| `eyebrow` | Project · area, a few words. |
| `title` | What the reader will understand, as a sentence. |
| `intro` | Two or three sentences: what the page covers and that every box and arrow is clickable. |
| `sourceNote` | HTML. What the page was built from (the findings, documents, code), the date, branch or commit, path prefixes used in refs. The evidence legend is added automatically. |

Text fields are inserted as text, except `sourceNote`, view `read` and `NOTES`, which are HTML. Never put `</script` or `<!--` in any string; the check rejects it.

## Views

One view is one diagram with its explanation. Views with the same `tab` are shown together on one tab, one after another, never behind a selector.

| Field | Required | What it is |
|---|---|---|
| `id` | yes | Lowercase, digits, dashes. Unique. |
| `tab` | yes | Tab name. Views sharing it render in order on that tab. |
| `title` | yes | The view's scope, e.g. "Components of the Order API". |
| `purpose` | yes | The question this view answers. |
| `read` | yes | How to read it: shapes, arrows, what is left out. HTML allowed. |
| `scope` | no | What was inspected and what was omitted. |
| `gap` | when nodes are empty | What is missing and what input would fill it. A view with a gap and no nodes is valid; an invented diagram is not. |
| `parent`, `focus` | no | `parent` is the view this one zooms into; `focus` is the key of the element in the parent that this view expands. Both pages get "Part of" / "Zoom in" links and the popup of the focal element links here. |
| `arrow` | no | Overrides the one-line arrow convention shown first in the legend. |
| `trace` | no | `{ out: "…", in: "…" }` button labels for reachability tracing. Presets set them for module graphs and lineage. |
| `nodes`, `edges`, `groups` | | See below. |
| kind fields | per kind | `level`, `notation`, `pipeline`, `module`. See the skill's SKILL.md. |

The legend is generated from the node types, edge kinds and statuses the view uses. A text list of every relationship is generated under each diagram.

## Nodes, groups and edges

**Node**

| Field | What it is |
|---|---|
| `id` | Unique in the view. Edges and the tour refer to it. |
| `key` | The model identity across views; defaults to `id`. Nodes with the same key are the same element: they must have the same `label`, and the popup links between them. Use different keys for different things even if names look alike. |
| `type` | A node type from the preset (below) or from `TYPES`. |
| `label` | Name. Wraps to two lines at most. |
| `sub` | One short line under the name: technology, path, table name. |
| `short` | One or two lines of what it does, shown in the box. |
| `detail` | Longer text for the popup only. |
| `members`, `ops` | For class-shaped types: attribute lines and operation lines, monospace. |
| `provides`, `requires` | For UML components: interface names drawn as lollipops (right) and sockets (left). Twelve characters at most. |
| `col`, `row`, `w`, `h` | Grid position and span (w, h default 1). |
| `group` | The id of the boundary it sits in. |
| `ev`, `status`, `refs` | Evidence. See below. |

A node repeated in another view (same key) may leave out `short`, `detail` and `refs`; the popup borrows them from its counterpart.

**Group** (a boundary: a system, a container, a module): `{ id, label, col, row, w, h, parent?, dashed? }`. It covers whole grid cells; its nodes must lie inside and declare `group`. Nest two levels at most. Containment is always a group, never an edge.

**Edge**

| Field | What it is |
|---|---|
| `id` | Optional; defaults to `e<index>` in the view's edge list. Give one when the tour refers to it. |
| `from`, `to` | Node ids in the same view. |
| `kind` | An edge kind from the preset or `EDGE_KINDS`. |
| `label` | What it carries or does: the data, the call, the import, the relationship verb. Short. |
| `fromEnd`, `toEnd` | Counts for kinds with ends: `1`, `0..1`, `0..*`, `1..*`, `?` for unknown. The count next to an element is how many of it relate to one instance at the other end. |
| `via` | `[[col, row], …]` bend points. Half values (`1.5`) land in the gap between cells; use them to route around a box. |
| `cycle` | Lineage only: why a loop exists. |
| `ev`, `status`, `refs`, `detail` | As for nodes. |

## Layout on the grid

Each cell is 192 × 104 px with a 140 px column gap and an 84 px row gap. Lay the main path left to right or top to bottom. Put context (people, external systems, other modules) on the outside. Rules that keep it readable:

- Neighbours on the same row get labels up to about 20 characters per line; vertical neighbours fit three lines of 24.
- Keep straight edges free of other boxes. The check reports every edge that crosses a box and every label that sits on a box or another label; fix them with a different `col`/`row` or a `via` through a gap.
- A class with more than about four members needs `h: 2`. The check gives the height needed.
- Two edges between the same pair (a read and a write, a cycle) are drawn side by side with their labels spread along the line.
- On a phone (under 768 px) a diagram scrolls inside its frame; from 768 px up it is drawn at full size and a wide diagram makes the page scroll sideways. Do not squeeze diagrams. Split a crowded view into two scoped views on the same tab instead.

## Node types and edge kinds per kind

| kind | Node types | Edge kinds |
|---|---|---|
| `c4` | `person`, `system`, `external-system`, `container`, `database`, `component`, `code`, `external-code`, `uml-component`, `uml-interface` | `uses`, `async`, `code-dep`, `inherits`, and for the UML view `dependency`, `realization`, `assembly`, `delegation` |
| `data-flow` | DFD: `entity`, `process`, `store`. Lineage: `dataset`, `job`, `consumer`. Pipeline: `source`, `stage`, `artifact`, `dataset`, `scheduler` | `flow` (DFD), `derives` (lineage), `data` and `trigger` (pipeline) |
| `module-dependency` | `module`, `part`, `contract`, `resource`, `external`, `unresolved` | `imports`, `type`, `runtime`, `calls`, `build`, `test` |
| `data-model` | `concept`, `entity`, `table`, `class`, `value`, `enum`, `interface` | `relates` (conceptual), `erd`, `erd-weak` (crow's foot), `association`, `navigable`, `aggregation`, `composition`, `generalization`, `realization`, `dependency` |

Each preset fixes shape, colour, line style and arrowheads, so the same element type looks the same on every page. The legend shows each kind's meaning. A custom type goes in `TYPES` as `{ label, shape, color, tint }` with a palette pair from the template (`blue`, `violet`, `teal`, `orange`, `rose`, `amber`, `indigo`, `slate`, `green`, `sky`); the check verifies its contrast.

## Evidence marks and status

Every node and edge carries `ev`, one of:

| `ev` | Meaning |
|---|---|
| `code+check` | read in code and re-checked by hand |
| `code` | traced in code, line numbers not all re-checked |
| `docs` | taken from docs or specs only |
| `inferred` | reasoned from code, not run |

- Carry over the marks the findings already have. Without marks, use `docs` for what came from documents or the user's description, and `inferred` for what you concluded. Use `code+check` only for code this session actually re-read.
- `code` and `code+check` need `refs`: `path:line`, `path:symbol`, a document section or a URL.
- `status` is separate from evidence: `proposed` (a design, not built), `illustrative` (an invented example), `unknown` (the element exists but its details are not known). Status draws a badge and a dashed or dotted border.

## Tour, quiz, glossary, sources, notes

- `TOUR`: `{ view, nodes: [ids], edges: [ids], text }` steps of a guided walk-through. Three to six steps that follow one real path through the views. The tour highlights the listed items and dims the rest.
- `QUIZ`: `{ q, a }` questions with a revealable answer. Ground every answer in the diagram.
- `GLOSSARY`: `[ term, meaning ]` pairs for terms the reader may not know.
- `SOURCES`: `{ label, href?, note? }` for the findings, documents and notation references used.
- `NOTES`: optional HTML shown after the views: sample records, an input/output table, a worked example. Mark invented values as illustrative.

## What the checks catch

`page.mjs` (static, on the data):

- Structure: missing constants, unknown kind, view, node, group, type or edge kind; duplicate ids; edges to missing nodes; tour items that do not exist; empty views without a gap; template text left over.
- Layout: overlapping boxes, nodes outside their group or straddling a boundary, edges crossing boxes, labels on boxes or on each other, text too long for its box, too many members for the height.
- Evidence: missing or unknown `ev`, `code` marks without refs, illustrative items marked as code, the same key with different names in different views.
- Kind rules: C4 levels and allowed element types, one focal system at L1, L3/L4 parents and focus; DFD flows that bypass a process, processes without input or output, context-view shape, balancing of boundary flows with the parent; lineage loops without a reason; pipeline ETL/ELT label; module cycles (reported) and internals views tied to a module; data-model levels and notations, missing counts at relationship ends, keys in a conceptual view, UML operations without code evidence.

`screenshot.mjs` (rendered, in headless Chromium): every tab at desktop width and at 390 px, console errors, labels overlapping boxes or each other as actually drawn, text spilling out of a box, sideways page scrolling on a phone, and the popup opening on click and closing on Escape.

## Look at it in a browser

Run `screenshot.mjs` and open the PNGs it writes. It needs the `playwright` package: `npm i -D playwright && npx playwright install chromium` in a scratch folder, or set `PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs` (and `CHROMIUM_PATH` when the installed browser build does not match). With a Playwright or Chrome browser tool in the session you can use it instead; serve the folder with `python3 -m http.server` because `file://` is often blocked.

On the screenshots, check what the scripts cannot judge: whether the layout reads in the intended direction, whether the main path is obvious, and whether each view answers its `purpose`. If no browser can run, say that the page was checked only statically.

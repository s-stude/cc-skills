---
name: module-dependency
description: Turn findings about a project's modules (from this session, notes, docs, manifests or code the user points at) into an interactive single-file HTML page with the module dependency graph, the inside of each module, and dependency/dependent tracing, built from a shared template and validated by scripts. Use when the user wants to learn or explore how modules fit together, what each one needs, what needs it, where the cycles are, or what a change may affect. Not for runtime flows (use learn-repo:flow-diagram), C4 architecture levels (learn-repo:c4-model) or package vulnerability audits.
---

# Learn module dependencies

The output is one HTML page that answers: what are the modules, what is inside each one, what does each need, and who needs it. Every box and arrow is clickable and shows its evidence; a module's popup lists its direct dependencies and dependents and can trace everything reachable either way. The page comes from the template shared by all learn-repo page skills; you write only the data.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Below, `<root>` means that path and `<kind>` is `module-dependency`.

- `<root>/shared/assets/learn-page.html`: the template shared by all learn-repo page skills (page, styles, interactions, notation presets). Never edited per page.
- `<root>/shared/examples/module-dependency.data.js`, `<root>/shared/examples/module-dependency.html`: a complete fictional page of this kind to start from.
- `<root>/shared/scripts/page.mjs`: builds the page from a data file and runs the static checks.
- `<root>/shared/scripts/screenshot.mjs`: renders every tab in headless Chromium and checks the drawn result.
- `<root>/shared/references/page-data.md`: data fields, layout grid, notation, evidence marks, the checks.
- [references/dependency-semantics.md](references/dependency-semantics.md): arrow direction, kinds of evidence and dependency, cycles and change impact.

## 1. Build the model from the findings

The user sets the scope, usually by doing the analysis first and then asking for the page. Work from those findings and the manifests, imports or documents they name. Open code only to confirm a fact a box needs, and mark what you re-read `code+check`. When a box needs a fact the findings do not have, list every such gap in one question, or show the element with `status: "unknown"` or the view with a `gap`. Never invent files, symbols or line numbers.

Read [references/dependency-semantics.md](references/dependency-semantics.md), then list:

- Modules at one stated granularity (file, package, build target or subsystem), each with a stable `key`, responsibility and public surface. External packages are `external`; imports that could not be resolved are `unresolved`.
- Edges `A → B` meaning A depends on B, one per relationship kind: `imports`, `type` (type-only), `runtime` (dynamic import, DI, plugin), `calls` (across a process or network), `build`, `test`. Keep several kinds between the same pair as separate edges. Label each with what is consumed.
- For each module worth opening: its parts (`part`), contracts (`contract`), resources (`resource`) and which parts cross the boundary.

Draw only direct edges. Indirect reach is shown by the trace buttons, never by an extra edge. Keep cycles; do not cut an edge to make the graph acyclic. A partial inspection supports "no cycle in what was inspected", nothing more. Put the inspected scope and the snapshot (commit or date) in the view's `scope` and in `sourceNote`.

## 2. Views

The graph and an internals view per important module, by default. Each view sets `notation`.

| notation | tab | Shows | Fields |
|---|---|---|---|
| `graph` | Module graph | Modules grouped by an evidenced boundary (a group per layer or package), external and unresolved targets. For a large graph, an overview view plus focused neighbourhood views on the same tab, each stating what it leaves out. | `scope` |
| `internals` | Inside &lt;module&gt; | A group for the module boundary with its parts inside; the modules it depends on outside the group; edges that cross the boundary. | `module` the module key, `parent` the graph view, `focus` the module key |

Containment is a group, never an edge. Use the words "depends on" and "needed by" rather than upstream and downstream. Do not label a dependency a violation unless the findings state the rule it breaks, and do not turn the page into a refactoring proposal.

## 3–5. Build, look, hand over

Read `<root>/shared/workflow.md` and follow it, with `<root>` = `${CLAUDE_PLUGIN_ROOT}` and `<kind>` = `module-dependency`. It is the same for every learn-repo page skill: write the data file, build and check it with `page.mjs`, render and check it with `screenshot.mjs`, then hand over.

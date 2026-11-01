---
name: c4-model
description: Turn architecture findings (from this session, notes, docs or code the user points at) into an interactive single-file HTML page with C4 levels 1–4 and a UML component view, built from a shared template and validated by scripts. Use when the user asks to visualize, draw or explain system context, containers, components, code structure or component interfaces, or says "C4". Not for runtime flows or swimlanes (use learn-repo:flow-diagram), module import graphs (learn-repo:module-dependency), data movement (learn-repo:data-flow) or entities and tables (learn-repo:data-model).
---

# Learn C4 model

The output is one HTML page with a tab per C4 level (L1 context, L2 containers, L3 components, L4 code) and a tab for a UML component view. Every box and arrow is clickable and shows its evidence. The page comes from the template shared by all learn-repo page skills; you write only the data.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Below, `<root>` means that path and `<kind>` is `c4`.

- `<root>/shared/assets/learn-page.html`: the template shared by all learn-repo page skills (page, styles, interactions, notation presets). Never edited per page.
- `<root>/shared/examples/c4.data.js`, `<root>/shared/examples/c4.html`: a complete fictional page of this kind to start from.
- `<root>/shared/scripts/page.mjs`: builds the page from a data file and runs the static checks.
- `<root>/shared/scripts/screenshot.mjs`: renders every tab in headless Chromium and checks the drawn result.
- `<root>/shared/references/page-data.md`: data fields, layout grid, notation, evidence marks, the checks.
- [references/diagram-semantics.md](references/diagram-semantics.md): what each C4 level and the UML component view may contain.

## 1. Build the model from the findings

The user sets the scope, usually by doing the analysis first and then asking for the page. Work from those findings and the documents or code they name. Open code only to confirm a fact a box needs, and mark what you re-read `code+check`. When a box needs a fact the findings do not have, list every such gap in one question, or show the element with `status: "unknown"` or the view with a `gap`. Never invent classes, interfaces, technologies or file references.

Read [references/diagram-semantics.md](references/diagram-semantics.md), then list:

- Elements with one stable `key` each: people, the focal system, external systems, containers, components, code elements. The same element keeps its key and name in every view.
- Relationships with a concrete label ("Submits orders [JSON/HTTPS]"), the protocol when known, and the evidence.
- For the UML view: interfaces each component provides and requires, only where the findings name them.

Keep the current implementation and a proposed design apart (`status: "proposed"`). Point out contradictions between sources instead of merging them.

## 2. Views

All five by default. Each view sets `level`. A level with too little evidence keeps its view with a `gap`.

| level | tab | Shows | Links |
|---|---|---|---|
| `L1` | L1 Context | The one focal `system`, `person`s, `external-system`s | |
| `L2` | L2 Containers | `container`s and `database`s inside a group for the system, plus people and external systems | `parent` the L1 view, `focus` the system key |
| `L3` | L3 Components | `component`s inside a group for one container, plus what that container talks to | `parent` the L2 view, `focus` the container key |
| `L4` | L4 Code | `code` elements of one component, `external-code` for shared code | `parent` the L3 view, `focus` the component key |
| `UML` | UML components | `uml-component`s with `provides`/`requires`, `assembly`, `dependency`, `realization`, `delegation` edges | |

For a large system give each container its own L3 view and each important component its own L4 view, all on the same tab. They render one after another, each with its own title and scope. C4 views use `uses`, `async`, `code-dep` and `inherits` edges; the UML view uses only the UML kinds.

## 3–5. Build, look, hand over

Read `<root>/shared/workflow.md` and follow it, with `<root>` = `${CLAUDE_PLUGIN_ROOT}` and `<kind>` = `c4`. It is the same for every learn-repo page skill: write the data file, build and check it with `page.mjs`, render and check it with `screenshot.mjs`, then hand over.

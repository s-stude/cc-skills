---
name: data-flow
description: Turn findings about how data moves and changes (from this session, notes, docs, SQL, schemas or code the user points at) into an interactive single-file HTML page with a data flow diagram (context and decomposition), a data lineage graph and an ETL/ELT pipeline view, built from a shared template and validated by scripts. Use when the user wants to see or teach where data comes from, how it is transformed, where it is stored and what consumes it, or to trace an output back to its sources. Not for request or process swimlanes (use learn-repo:flow-diagram), schema-only entity diagrams (learn-repo:data-model) or code structure (learn-repo:c4-model, learn-repo:module-dependency).
---

# Learn data flow

The output is one HTML page that shows one scenario three ways: a DFD (what data crosses the boundary and which processes change it), a lineage graph (which inputs an output is derived from), and the ETL/ELT pipeline (the stages in order). Every box and arrow is clickable and shows its evidence. The page comes from the template shared by all learn-repo page skills; you write only the data.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Below, `<root>` means that path and `<kind>` is `data-flow`.

- `<root>/shared/assets/learn-page.html`: the template shared by all learn-repo page skills (page, styles, interactions, notation presets). Never edited per page.
- `<root>/shared/examples/data-flow.data.js`, `<root>/shared/examples/data-flow.html`: a complete fictional page of this kind to start from.
- `<root>/shared/scripts/page.mjs`: builds the page from a data file and runs the static checks.
- `<root>/shared/scripts/screenshot.mjs`: renders every tab in headless Chromium and checks the drawn result.
- `<root>/shared/references/page-data.md`: data fields, layout grid, notation, evidence marks, the checks.
- [references/diagram-semantics.md](references/diagram-semantics.md): DFD, lineage and ETL/ELT rules and common confusions.

## 1. Build the model from the findings

The user sets the scope, usually by doing the analysis first and then asking for the page. Work from those findings and the documents, SQL or code they name. Open code only to confirm a fact a box needs, and mark what you re-read `code+check`. When a box needs a fact the findings do not have, list every such gap in one question, or show the element with `status: "unknown"` or the view with a `gap`.

Read [references/diagram-semantics.md](references/diagram-semantics.md), then list:

- Sources, processes or jobs, stores or datasets, and consumers, each with one stable `key`. A dataset keeps its key and name in every view.
- Directed flows named by the data they carry. Data dependencies and execution order are different things; a "runs after" link is a `trigger` edge in the pipeline view only.
- The transformations: validation, filtering, joining, aggregation, enrichment, masking, with the expression where the findings have it. Put field-level lineage in the `detail` of a dataset or job, and only where an expression or metadata establishes it.
- One representative record followed end to end. Put its input and output in `NOTES`, marked illustrative; for an aggregate, say it contributes to a total rather than being the total.

Code shows what can happen, not that a production run did. Do not add timestamps, row counts or schedules the findings do not state.

## 2. Views

All three notations by default. Each view sets `notation`. A notation the findings cannot support keeps its view with a `gap`; never present an ordinary request path as ETL to fill the tab.

| notation | tab | Shows | Fields |
|---|---|---|---|
| `dfd` | DFD | Context view: the system as one `process`, the `entity`s around it, no stores. Decomposition view: the internal `process`es and `store`s, with the same boundary flows. Edges `flow`. | Context sets `level: "context"`. Decomposition sets `parent` to the context view and `focus` to its process key. |
| `lineage` | Lineage | `dataset` → `job` → `dataset` chains, ending at a `consumer`. Edges `derives`. Upstream and downstream tracing come with the preset. | `cycle: "why"` on an edge of any loop |
| `pipeline` | ETL pipeline | `source`/`dataset` → `stage`s → target `dataset`, `artifact`s for staging and quarantine, a `scheduler` with `trigger` edges. Edges `data`. | `pipeline: "ETL"`, `"ELT"` or `"hybrid"` |

Every DFD flow must touch a process. Boundary flows in the decomposition must match the context view by entity key and label (the checks compare them).

## 3–5. Build, look, hand over

Read `<root>/shared/workflow.md` and follow it, with `<root>` = `${CLAUDE_PLUGIN_ROOT}` and `<kind>` = `data-flow`. It is the same for every learn-repo page skill: write the data file, build and check it with `page.mjs`, render and check it with `screenshot.mjs`, then hand over.

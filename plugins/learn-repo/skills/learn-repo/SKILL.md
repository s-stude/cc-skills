---
name: learn-repo
description: Pick the right learn-repo page for findings about a codebase and hand over to it. Use when the user asks to visualize, diagram or explain the repo or a part of it as an HTML learning page without naming which kind (architecture, data, modules, a flow), or asks what learn-repo can draw.
---

# Learn repo

Five skills in this plugin turn findings into one interactive HTML page each. The user sets the scope, usually by doing the analysis first. Pick by the question the reader wants answered:

| Question | Skill | Page |
|---|---|---|
| What is the system made of, from context down to code? | `learn-repo:c4-model` | C4 L1–L4 and a UML component view |
| Where does this data come from, how does it change, who reads it? | `learn-repo:data-flow` | DFD (context and decomposition), lineage, ETL/ELT pipeline |
| What are the entities, tables or classes and how do they relate? | `learn-repo:data-model` | Conceptual, logical and physical views in ERD and UML class notation |
| What modules exist, what does each need, what needs it? | `learn-repo:module-dependency` | Module graph, module internals, dependency tracing |
| What happens, step by step, when someone does X? | `learn-repo:flow-diagram` | Swimlane map of one run through the layers |

- One request can need two pages, for example the data model and the flow that writes it. Make them one after another with the two skills.
- If the request fits none of them (a chart of measurements, a state machine), say so instead of forcing a page.
- If it is unclear which question the user is asking, ask once, naming the two closest options.

Invoke the chosen skill with the Skill tool and follow it. The four page skills (`c4-model`, `data-flow`, `data-model`, `module-dependency`) share one template, one build-and-check script and the same look; `flow-diagram` has its own swimlane template.

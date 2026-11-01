---
name: data-model
description: Turn findings about a domain's data (from this session, business rules, docs, DDL, migrations, ORM or source code the user points at) into an interactive single-file HTML page with conceptual, logical and physical views in ERD (crow's foot) and UML class notation, built from a shared template and validated by scripts. Use when the user wants to learn, understand or visualize entities, tables, classes and their relationships and cardinalities. Not for data movement (use learn-repo:data-flow), runtime flows (learn-repo:flow-diagram), migrations or query writing.
---

# Learn a data model

The output is one HTML page that teaches a data model from business meaning down to storage: a conceptual view, a logical and a physical view, in ERD and UML class notation. Every entity and relationship is clickable and shows its rule, evidence and counterparts in the other views. The page comes from the template shared by all learn-repo page skills; you write only the data.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Below, `<root>` means that path and `<kind>` is `data-model`.

- `<root>/shared/assets/learn-page.html`: the template shared by all learn-repo page skills (page, styles, interactions, notation presets). Never edited per page.
- `<root>/shared/examples/data-model.data.js`, `<root>/shared/examples/data-model.html`: a complete fictional page of this kind to start from.
- `<root>/shared/scripts/page.mjs`: builds the page from a data file and runs the static checks.
- `<root>/shared/scripts/screenshot.mjs`: renders every tab in headless Chromium and checks the drawn result.
- `<root>/shared/references/page-data.md`: data fields, layout grid, notation, evidence marks, the checks.
- [references/modeling-guide.md](references/modeling-guide.md): abstraction levels versus notations, reading cardinality, constraints versus business rules, UML relationships.

## 1. Build the model from the findings

The user sets the scope, usually by doing the analysis first and then asking for the page. Work from those findings and the schemas, migrations or classes they name. Open code only to confirm a fact a box needs, and mark what you re-read `code+check`. When a box needs a fact the findings do not have, list every such gap in one question, or show the element with `status: "unknown"` or the view with a `gap`. A missing DBMS or missing classes do not block the conceptual and logical views.

Read [references/modeling-guide.md](references/modeling-guide.md), then list:

- Concepts, entities, tables, classes and value types. Give the same concept the same `key` in every view so the popup links them, but do not assume one concept is one class is one table: an embedded value has no table, a concept can span several tables.
- Relationships with a verb label and the count at both ends (`1`, `0..1`, `0..*`, `1..*`, `?` when unknown). Write both readings before drawing them. Never turn an unknown count into `0..*`.
- For each rule, whether the schema enforces it or it is a business rule only. Say which in the relationship's `detail`.
- Nonrelational structure (embedded documents, references, graphs) as it really is, with a sentence in `read` on which ERD ideas do not apply.

Keep the existing implementation, the stated intent and any proposed design apart (`status: "proposed"`), and keep normalization advice out of a description of what exists.

## 2. Views

All by default. Each view sets `level` and `notation`. A level the findings do not cover keeps its view with a `gap`.

| level | notation | tab | Shows | Edges |
|---|---|---|---|---|
| `conceptual` | `concept` | Conceptual | `concept`s and business relationships, no keys or types | `relates` with counts |
| `logical` | `erd` or `uml` | Logical ERD / UML classes | `entity`s with attributes and identifiers, independent of a DBMS; or domain `class`es, `value`s, `enum`s | ERD: `erd` (identifying), `erd-weak`. UML: `association`, `navigable`, `aggregation`, `composition`, `generalization`, `realization`, `dependency` |
| `physical` | `erd` | Physical ERD | `table`s with PK, FK, types, nullability and unique keys as the storage defines them | `erd`, `erd-weak` |

Provide at least one ERD view and one UML class view. When there are no source classes, label the UML view a domain model and leave out operations; operations need a `code` mark. Composition needs evidence of ownership, not just a foreign key or cascade delete. A class with more than four members needs `h: 2`.

## 3–5. Build, look, hand over

Read `<root>/shared/workflow.md` and follow it, with `<root>` = `${CLAUDE_PLUGIN_ROOT}` and `<kind>` = `data-model`. It is the same for every learn-repo page skill: write the data file, build and check it with `page.mjs`, render and check it with `screenshot.mjs`, then hand over.

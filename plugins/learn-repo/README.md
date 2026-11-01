# learn-repo plugin

Claude Code plugin with five skills that turn findings about a codebase into interactive single-file HTML learning pages:

| Skill | Page |
|---|---|
| `learn-repo:learn-repo` | Picks the right page skill for a request |
| `learn-repo:c4-model` | C4 L1–L4 and a UML component view |
| `learn-repo:data-flow` | DFD, lineage and ETL/ELT pipeline |
| `learn-repo:data-model` | Conceptual, logical, physical views in ERD and UML class notation |
| `learn-repo:module-dependency` | Module graph, module internals, dependency tracing |
| `learn-repo:flow-diagram` | Swimlane map of one run through the layers |

The four page skills share `shared/`: the page template, `page.mjs` (build, check, extract), `screenshot.mjs` (rendered checks in headless Chromium), the data reference, the common build/look/hand-over steps (`workflow.md`) and one worked example per kind. Skills reach it through `${CLAUDE_PLUGIN_ROOT}`. `flow-diagram` keeps its own template and scripts in its skill folder.

This is a copy of the project skills in `../../skills/learn-*`. The two are not synced; edit the one you use.

## Use it

```bash
claude --plugin-dir skill-plugins/learn-repo      # loads in place; /reload-plugins after edits
claude plugin validate skill-plugins/learn-repo
```

## Test it

```bash
node skill-plugins/learn-repo/shared/check.mjs           # rebuild and check the example pages
node skill-plugins/learn-repo/shared/check.mjs --check   # check only
```

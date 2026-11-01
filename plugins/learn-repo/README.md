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

## Install

The marketplace file is `../.claude-plugin/marketplace.json` (marketplace `skill-plugins`, next to this folder).

From a local checkout, read in place, so edits need only `/reload-plugins`:

```bash
claude plugin marketplace add <path>/skill-plugins
claude plugin install learn-repo@skill-plugins
```

From a GitHub repository whose root holds the `skill-plugins` content, at the prompt of a terminal session:

```
/plugin install learn-repo --marketplace <owner>/<repo>
```

or from a shell: `claude plugin install learn-repo --marketplace <owner>/<repo>`.

For one session without installing: `claude --plugin-dir <path>/skill-plugins/learn-repo`.

## Test it

```bash
node <path>/skill-plugins/learn-repo/shared/check.mjs           # rebuild and check the example pages
node <path>/skill-plugins/learn-repo/shared/check.mjs --check   # check only
```

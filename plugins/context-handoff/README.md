# context-handoff plugin

Claude Code plugin that moves work to a fresh session before the context runs out. It ships two parts that work together:

| Part | What it does |
|---|---|
| Skill `context-handoff:handoff-to-new-session` | Writes a numbered brief in `.handoffs/brief-NNN.md` (goal, rules, done, remaining, decisions, workflow, environment) and opens a new agterm session that continues from it. Run it any time with `/context-handoff:handoff-to-new-session` or by asking to "hand off". |
| Mod (`hooks/register.ts`) | After a turn where context usage reaches 80% or more, sends a prompt as if you typed it, asking Claude to hand off with the skill above. |

## Requires agterm

The handoff relies on [agterm](https://agterm.com), a macOS terminal app, to open the new session. The skill uses its `agtermctl` CLI to open a session next to the current one, start Claude there with the brief, and bring over a peer (such as Codex) running in the split pane. Run Claude Code inside agterm to get this.

Without agterm (not installed, or Claude Code running in another terminal), the skill still writes the brief, then tells you plainly that it could not open the session and prints the steps to start it yourself, with the brief's full path:

```
1. Open a new terminal window or tab.
2. Run:
     cd /path/to/project
     HANDOFF_SEQ=004 claude
3. Send Claude this first message:
     Read /path/to/project/.handoffs/brief-004.md and continue the work it hands over: start with its first steps.
```

## Behaviour

The mod sends once, then re-arms when context drops below 80% again (for example after `/compact`). A new session (`/clear` or restart) starts fresh. To change the threshold or text, edit `THRESHOLD` and `MESSAGE` in `hooks/register.ts`.

## Install

The marketplace file is `../.claude-plugin/marketplace.json` (marketplace `skill-plugins`, next to this folder).

From a local checkout, read in place, so edits need only `/reload-plugins`:

```bash
claude plugin marketplace add <path>/skill-plugins
claude plugin install context-handoff@skill-plugins
```

From a GitHub repository whose root holds the `skill-plugins` content, at the prompt of a terminal session:

```
/plugin install context-handoff --marketplace <owner>/<repo>
```

### For one project only

The commands above install for you in every project (`user` scope). To limit the plugin to one project, run both commands from inside that project with `--scope`:

```bash
cd /path/to/project
claude plugin marketplace add <path>/skill-plugins --scope local
claude plugin install context-handoff@skill-plugins --scope local
```

| Scope | Recorded in | Who gets it |
|---|---|---|
| `local` | `.claude/settings.local.json` | Only you, only in this project |
| `project` | `.claude/settings.json` | Everyone who opens the project, once that file is committed |
| `user` (default) | `~/.claude/settings.json` | You, in every project |

Use `project` with a GitHub marketplace source (`<owner>/<repo>`), not a local path: teammates don't have your checkout. Remove it with `claude plugin uninstall context-handoff --scope local` (or `project`).

### Without installing

For one session without installing: `claude --plugin-dir <path>/skill-plugins/context-handoff`.

## Test it

```bash
claude plugin validate <path>/skill-plugins/context-handoff
claude plugin test <path>/skill-plugins/context-handoff
```

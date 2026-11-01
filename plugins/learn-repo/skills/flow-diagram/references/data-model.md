# Flow diagram data model

Everything a diagram changes sits in `assets/flow-template.html` between `// ===== DATA START =====` and `// ===== DATA END =====`, plus two HTML blocks marked `CARDS` and `LIMITS`. The engine below the data block is generic; leave it alone unless the user asks for a new kind of mark.

## Contents

1. [PAGE](#page)
2. [LANES](#lanes)
3. [TAGS](#tags)
4. [STEPS](#steps)
5. [SCENARIOS](#scenarios)
6. [CARDS and LIMITS](#cards-and-limits)
7. [Writing the texts](#writing-the-texts)
8. [Worked example](#worked-example)

## PAGE

| Field | What it is |
|---|---|
| `eyebrow` | Product · area · subsystem. Three or four words in the small caps line above the title. |
| `title` | A question or a "what happens when …" sentence. The reader should recognise the action they take. |
| `intro` | Two or three sentences: where the action starts, which layers it crosses, where it ends, and that boxes are clickable. |
| `sourceNote` | HTML. Which documents or code the diagram was built from, the date and branch or version, the path prefixes used in refs, and the evidence marks legend. This is the diagram's provenance; never leave it as template text. |
| `legend` | The four legend phrases. Change them only when the visual means something else in this diagram. |

## LANES

One lane per layer of the system the flow crosses. Order them by distance from the user: what the user touches on the left, external services and storage on the right. Four to eight lanes; the map is 214 px per lane and scrolls horizontally past about seven.

| Field | What it is |
|---|---|
| `id` | Short identifier used by steps and side effects. |
| `name` | Lane header, two or three words. |
| `sub` | One line under the header: the files, processes or components the lane stands for. Up to about 34 characters; longer text wraps to a second, smaller line and is cut after two. |
| `color` | A saturated hue that stays readable as white text on it. |
| `tint` | A very light wash of the same hue for the lane background and the box header. |

A lane may hold only side effects (an external API, a database). That is fine and common.

A palette that reads as seven distinct, vibrant lanes on a light page:

| Role | color | tint |
|---|---|---|
| user interface | `#1d4ed8` | `#e8efff` |
| transport | `#7c3aed` | `#f1eaff` |
| server entry | `#d9480f` | `#fff0e8` |
| deterministic logic | `#047857` | `#e3f7ef` |
| probabilistic or orchestration logic | `#c2187a` | `#fde8f3` |
| external service | `#dc2626` | `#ffe9e9` |
| data and logs | `#0e7490` | `#e2f6fb` |

Keep red for the lane whose use costs money or leaves the system (an LLM API, a payment provider). Readers scan for it.

## TAGS

Small badges in a step's title bar that say who decides at that step. Define only the ones the flow uses; the legend lists the ones in use.

| Field | What it is |
|---|---|
| `label` | Two to five characters: `LLM`, `YOU`, `CRON`, `3RD`. |
| `color`, `bg` | Badge colour and the light background used in the list and detail panel. |
| `legend` | The phrase shown in the legend. |

## STEPS

One step is one thing the reader can observe or point at in the code: a message leaves, a handler checks something, a model is asked, a file is written. Twelve to thirty steps, numbered in the order they happen on the full path. Under about ten a numbered list serves better than a map; over about thirty, split the flow in two diagrams.

| Field | Required | What it is |
|---|---|---|
| `n` | yes | 1..N in order. The engine draws the arrow from each step to the next. |
| `lane` | yes | A lane id. |
| `title` | yes | ≤ 40 characters. A verb phrase in the reader's words, not a function name: "Handler receives the request", not "onMessage". A single word longer than about 18 characters (an identifier) breaks mid-word; put identifiers in `box` or `refs`. |
| `box` | yes | ≤ 90 characters. The concrete what: the shape of the data, the limits, the names that matter. This is what a reader sees without clicking. |
| `detail` | yes | Two to five sentences for the detail panel and the list: what goes in, what comes out, what is deliberately not done. |
| `refs` | yes | Files, functions, line ranges, document sections. Use the path prefixes declared in `sourceNote`. Line numbers drift; a function name next to the path survives longer. |
| `ev` | yes | Evidence mark: `✓` read in code and re-checked by hand, `code` traced in code, `docs` from documents only, `inferred` reasoned, not run. Shown in the list and the panel. |
| `tag` | no | A key of `TAGS`. |
| `branch` | no | ≤ 140 characters. The stop, skip and fallback cases of this step as "cause → effect; cause → effect". Drawn as the dashed amber strip under the box. |
| `via` | no | Text on the arrow to the next step: the message name or call that carries the flow across a lane boundary. Use it whenever the next step is in another lane. |
| `also` | no | Side effects: `[{ lane, text, dir }]`. `text` ≤ 40 characters names the call, message or record; `dir` is `to` (this step causes it), `from` (this step reads it) or `both`. Several side effects stack vertically. |
| `loopTo` | no | Step number this step jumps back to (a retry, a rerun, a loop). Drawn as a dashed line down the left margin in the step's lane colour; each loop gets its own margin column. Keep to one or two: the reruns a reader can trigger. A retry job or an internal re-queue is branch text. |
| `loopLabel` | no | Text along the loop line. Say what is different on the second pass. |

## SCENARIOS

A scenario is a path through the same steps. The engine fades the steps not in `steps` and shows `notes` next to the steps that behave differently. Three to six scenarios:

- `all` first, with every step;
- the happy-path variants that skip stages (cache hit, rules cover everything, nothing to do);
- the degraded paths (a dependency down, a stop condition, a timeout);
- a rerun or retry, starting from the step that triggers it;
- any other caller that reuses the same core, showing only the shared steps.

| Field | What it is |
|---|---|
| `id`, `label` | Chip id and text. |
| `summary` | One paragraph shown under the chips: what is different, what the user ends up seeing, what it costs. |
| `steps` | Step numbers on the path. Build it with `without(ALL, [ … ])` so a renumbering shows up as an error in the check script. |
| `notes` | `{ stepNumber: "what this step does differently here" }`. Notes may reference steps outside `steps` to explain why they are skipped. A note or summary states only what the source says; when the source is silent and the sentence is a deduction, say so in the sentence ("not stated in the source; assumed from …"). |

## CARDS and LIMITS

Two HTML blocks under the map. Edit their contents; keep the classes so they match the page.

Cards are for facts that belong to the whole flow rather than one step: the messages between the parties with the step that sends each, the external calls per run with when each is skipped, the data structures that cross the module boundary (a `pre` block), and who else calls the same core. Two to four cards.

Limits is a closing bulleted list for the constraints a box cannot show: timeouts, sampling, silent failures, things the reader would assume and would be wrong about. Each bullet carries an evidence mark. Delete the section if the research has nothing of this kind.

## Writing the texts

- Write for a reader who knows the domain but did not do the research. Titles say what happens; boxes say with what; details say why and with which exceptions.
- Every number anywhere on the page, in a box, branch, scenario summary, note or card, and also counts written as words ("two pushes"), must come from the research or from code the session read, with a ref the reader can open. If the source does not give the number, leave it out rather than guess. A number that only the code gives belongs on a step marked `✓`, and `sourceNote` says that code was re-read.
- Keep the research's own numbering and order. Split a step only when it crosses a lane; a split inside one lane is two boxes saying one thing. Do not turn a limits bullet into a step: it becomes a `branch` on the step it constrains, or a line in LIMITS.
- Put every stop, skip and fallback into `branch`. A reader uses the diagram to answer "what happens when X fails"; a happy-path-only diagram cannot.
- A side effect is something another lane can observe: a call, a message, a row, a file. Internal bookkeeping is detail text, not a side box.
- The evidence mark is a promise. `✓` means the current session read that code path; `code` means it was traced but not every line re-checked; `docs` means only the source documents say so. When the research notes carry marks, carry them over; when they do not, mark `docs`.
- Keep the chip labels short enough to fit one row at 1400 px: six scenarios of two or three words each.

## Worked example

From a diagram of an "AI suggests dependencies during spreadsheet import" flow. Seven lanes: Import window, Desktop transport, Server handler, Rules & knowledge base, LLM pipeline, GigaChat API, Data & logs.

```js
{ n: 6, lane: "pipe", title: "Stage 0: identify the project type", tag: "LLM", ev: "✓",
	box: "distinct titles and headings → one KB type + confidence",
	detail: "One chat call with the distinct titles and group names. The model picks a project type from the knowledge base and gives a confidence. The dialog later shows this type.",
	branch: "confidence < 0.3, or a type the KB does not know (counted as 0.1) → empty result, run stops; call fails → mkd with 0.5; type given by the dialog → skipped",
	also: [ { lane: "llm", text: "Stage 0 chat call", dir: "to" } ],
	refs: [ "W/gigachat/suggestions.ts detectProjectType", "W/gigachat/prompts.ts buildProjectTypePrompt", "PROJECT_TYPE_MIN_CONFIDENCE = 0.3" ] },

{ n: 21, lane: "ui", title: "Pick another type → rerun", ev: "✓",
	box: "gigachat.suggest-deps.retry with projectType; everything but Stage 0 runs again",
	detail: "Changing the project type sends the same task list with the chosen type. The server trusts the choice, skips Stage 0 and reruns every other stage at full price.",
	also: [ { lane: "server", text: "feedback: type-change", dir: "to" } ],
	loopTo: 3, loopLabel: "rerun · same tasks, chosen type · skips Stage 0",
	refs: [ "D/renderer/Import/.../DependencySuggestions.jsx", "W/gigachat/handlers.ts:62-77" ] }
```

And a scenario:

```js
{
	id: "nollm", label: "GigaChat unavailable",
	summary: "The API key is unset. The handler warns and runs anyway: the project type defaults to mkd with confidence 0.5, every LLM stage is skipped, and the result is the rule links only, with no primary flags.",
	steps: without(ALL, [ 6, 9, 12, 13, 15, 17, 21 ]),
	notes: { 4: "logs \"GigaChat not available, running with knowledge base only\"", 6: "skipped: mkd, confidence 0.5", 18: "profile has 0 calls" }
}
```

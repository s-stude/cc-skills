# Build, look, hand over (shared by every learn-repo page skill)

`<root>` is the plugin root and `<kind>` the page kind; the SKILL.md that sent you here gives both.

## 3. Write the data file and build

Read `<root>/shared/references/page-data.md` before the first build: the data fields, the layout grid, the node types and edge kinds of this kind, the evidence marks and the full list of checks. Then:

```bash
ROOT=<root>
mkdir -p ./tmp/learn
cp $ROOT/shared/examples/<kind>.data.js ./tmp/learn/<name>.data.js
# replace the example with the model from step 1
node $ROOT/shared/scripts/page.mjs build ./tmp/learn/<name>.data.js docs/learn/<name>.html
```

- Write only the data file. The page, styles, interactions and notation come from `<root>/shared/assets/learn-page.html` and are the same for every learn-repo skill; do not edit or copy the template.
- `build` refuses to write while the data has errors. Fix every error. Treat warnings as defects unless you can say why one does not apply: most are a box crossed by an edge, a label on a box, text that does not fit, or a mark without a reference.
- Output goes to the path the user gives, otherwise `docs/learn/<kind>-<topic>.html`. The data file stays in `./tmp/learn/`. To change an existing page, `page.mjs extract` its data, edit, build again.
- `<root>/shared/examples/<kind>.data.js` and `<kind>.html` next to it are a complete fictional page of this kind. Do not carry its names into the user's page.

## 4. Look at it

```bash
node $ROOT/shared/scripts/screenshot.mjs docs/learn/<name>.html ./tmp/learn/shots-<name>
```

It opens every tab at desktop width and at 390 px, checks console errors, overlaps as actually drawn, text spilling out of boxes, sideways scrolling on a phone, and the popup (opens on click, closes on Escape). Fix what it reports, then open the screenshots and judge what a script cannot: does the main path read in one direction, does each view answer its purpose. If no browser can run, say the page was checked only statically.

## 5. Hand over

Report: the file path as a clickable link, the views it holds, the evidence counts the build printed, every view that shows a gap and what input would fill it, and that the page loads Tailwind from a CDN and needs network access. Do not change project code, dependencies or configuration to produce the page.

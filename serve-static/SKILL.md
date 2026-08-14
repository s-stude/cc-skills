---
name: serve-static
description: Serve a project's static files locally over HTTP using npx serve, setting up a package.json npm start script so the setup is repeatable. Use this whenever the user says "serve this as a static website", asks to host or preview static files, wants to view HTML pages in a browser, needs a local web server for a folder of HTML/CSS/JS, or when a task requires loading local pages over http:// instead of file:// (e.g. for browser automation or screenshot verification).
---

# Serve Static Files

Host a directory of static files over HTTP with `npx serve`. No install step is needed — `npx` fetches the `serve` package on first use.

## 1. Pick the directory to serve

Serve the directory that contains the site's `index.html`, not necessarily the project root:

1. If `package.json` has a `start` (or `serve`) script that already runs a static server, prefer `npm start` — the project has made its choice; don't second-guess it.
2. Otherwise look for the conventional content directories, in order: `src/`, `public/`, `dist/`, `build/`, `site/`, then the project root.
3. If several candidates contain an `index.html` and the intent is unclear, ask the user which one is the site.

## 2. Set up `npm start`

The server command belongs in `package.json`, not in one-off shell history — future sessions and humans then start the site the same way.

- If the project has no `package.json`, create a minimal one at the project root:

```json
{
  "name": "<project-dir-name>",
  "private": true,
  "scripts": {
    "start": "npx serve <dir> -l ${PORT:-3000}"
  }
}
```

- If `package.json` exists but has no `start` script, add the `start` script above (leave everything else untouched).
- If a `start` script already exists and serves the site, use it as-is. If `start` is taken by something else (e.g. a framework dev server), add the script under `"serve"` instead.

## 3. Start the server

```bash
npm start
```

- Default to port 3000; override with `PORT=<port> npm start`. If the project documents a port (README, CLAUDE.md, scripts), use that.
- Run it in the background (`run_in_background`), since the process never exits on its own.
- If the port is taken (`lsof -i :<port>` or the server exits with EADDRINUSE), first check whether the same site is already being served — if so, just use the running server. Otherwise pick the next free port rather than killing the other process.
- For single-page apps whose client-side router needs unknown paths to fall back to `index.html`, add `-s`.

## 4. Verify it's up

Don't assume the server started — `npx` may still be downloading, or the port may have been rejected. Poll until it responds:

```bash
curl -s -o /dev/null -w "%{http_code}" --retry 5 --retry-connrefused http://localhost:<port>/
```

A `200` means it's serving. Then give the user the URL: `http://localhost:<port>`.

## 5. Clean up

A background server outlives the task, holds the port, and confuses later sessions. When the task that needed the server is finished (or the user says they're done), stop it — kill the background shell you started it in.

Killing the shell is usually not enough: `npm start` and `npx` spawn the actual server as a child process that survives its parent. After stopping the shell, check the port and kill any survivor:

```bash
lsof -ti :<port> | xargs kill
```

If you took over an already-running server you didn't start, leave it alone.

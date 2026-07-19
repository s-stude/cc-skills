# Graceful Shutdown & Port Cleanup

> Topic guide for the **nodejs-architecture** skill. Read this when a Node
> process won't release its port (EADDRINUSE on restart), orphaned/zombie node
> processes hold ports, or you need signal handling and clean DB-pool shutdown.

Make a long-lived Node process release its port and close its DB connections no
matter *how* it stops. Framework-agnostic; copy into any project.

The ready-to-use code lives in the skill's `assets/`:
- `../assets/lifecycle.js` — the drop-in shutdown helper (copy it into the project)
- `../assets/lifecycle.test.js` — Vitest suite covering every trigger and edge case

Copy `lifecycle.js` into the target project, wire it into each process (below),
and keep the watchdog dev-only.

## The problem

In dev your server is rarely a direct child of the terminal. A typical command
buries it several layers deep:

```
concurrently → npm run → node --watch → node server.js   ← the process that holds the port
```

**Ctrl+C** works because the terminal signals the whole process group, so every
layer gets it. It breaks when termination hits a *single* process instead:

- the IDE "stop" button (`SIGTERM`/`SIGKILL` to one PID),
- closing the terminal window (`SIGHUP`),
- `kill <pid>` of a launcher,
- a wrapper crashing or being `kill -9`'d (untrappable — can't clean up).

One wrapper layer fails to forward the signal down. The real listener is
**orphaned** (reparented to init, `ppid` becomes `1`), keeps running, and
**holds the port forever** — the next start fails with `EADDRINUSE`.

Subtler trap: `node --watch` runs your script as a *child*. If the layers above
the watcher die but the watcher survives, the listener's `ppid` still points at a
live (orphaned) parent — so a naive `ppid === 1` check never fires.

### Core principle

> **A long-lived process must be able to terminate itself.** Don't rely on a
> signal always arriving from above. Give the process its own ability to notice
> "the session is over" and shut down cleanly.

## The three triggers

A robust shutdown fires on **any** of these:

1. **A termination signal** — `SIGINT`, `SIGTERM`, and importantly **`SIGHUP`**
   (terminal close), which many apps forget to handle.
2. **Orphaned to init** — `process.ppid === 1`, the direct parent died.
3. **The dev session leader is gone** — a known "session PID" (the top launcher)
   no longer exists. This survives the "watcher still alive" trap because it
   ignores intermediate layers.

Triggers 2 and 3 form a **dev-only watchdog** (a 1-second poll). They must be
disabled in production, where `ppid === 1` can be legitimate (your process may be
PID 1's direct child inside a container or under a supervisor).

## Wiring it into each process

Import the helper from `assets/lifecycle.js` and give it an `onShutdown` that
does the real cleanup. Keep the watchdog gated on dev.

**HTTP server** — stop accepting connections, then close the DB pool:

```js
import { installGracefulShutdown, sessionPidFromEnv } from './lifecycle.js';

const server = app.listen(PORT, () => logger.info(`listening on ${PORT}`));
const isDev = process.env.NODE_ENV !== 'production';

installGracefulShutdown({
  name: 'API server',
  logger,
  watchOrphan: isDev,
  sessionPid: isDev ? sessionPidFromEnv() : undefined,
  onShutdown: async () => {
    await new Promise((resolve) => server.close(resolve)); // stop new connections
    await db.destroy();                                    // close the DB pool
  },
});
```

**Background worker** — stop the loop, let in-flight work finish (bounded), then
close the DB:

```js
const isDev = process.env.NODE_ENV !== 'production';

installGracefulShutdown({
  name: 'worker',
  logger,
  watchOrphan: isDev,
  sessionPid: isDev ? sessionPidFromEnv() : undefined,
  forceExitMs: 16_000, // a bit beyond the drain window below
  onShutdown: async () => {
    running = false;                  // stop pulling new jobs
    let waited = 0;
    while (busy && waited < 15_000) { // wait for the current job
      await sleep(250);
      waited += 250;
    }
    await db.destroy();
  },
});
```

## Publish the session leader PID from the dev launcher

The watchdog's strongest trigger needs a stable PID to watch: the top launcher.
Make that launcher's own PID visible to every child via an env var. In POSIX
shells `$$` is the shell's PID; `exec` replaces the shell with the launcher, so
the launcher inherits that PID:

```jsonc
// package.json
{
  "scripts": {
    // DEV_SESSION_PID becomes concurrently's own PID; every child inherits it.
    // -k makes concurrently kill the others when one exits.
    "dev": "DEV_SESSION_PID=$$ exec concurrently -k \"npm:dev:api\" \"npm:dev:worker\" \"npm:dev:web\""
  }
}
```

Any descendant can read `process.env.DEV_SESSION_PID` and shut down the instant
that PID disappears — even if `node --watch` or `npm` layers between are still
alive. POSIX-only; on Windows use a small Node launcher that spawns the children
and passes its own `process.pid` in their env.

## Third-party dev servers you can't modify

Bundlers like Vite hold their own port and won't import the helper. Either:

- **Plugin hook** (preferred). Install the same watchdog from a dev-only plugin
  running inside the tool's own Node process:

  ```js
  // vite.config.js — apply: 'serve' keeps it out of production builds
  function releasePortOnSessionEnd() {
    return {
      name: 'release-port-on-session-end',
      apply: 'serve',
      configureServer(server) {
        const onEnd = async () => { await server.close(); process.exit(0); };
        for (const s of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(s, () => onEnd());
        const sid = Number(process.env.DEV_SESSION_PID);
        const watch = Number.isInteger(sid) && sid > 1;
        const alive = (p) => { try { process.kill(p, 0); return true; } catch (e) { return e?.code === 'EPERM'; } };
        setInterval(() => {
          if (process.ppid === 1 || (watch && !alive(sid))) onEnd();
        }, 1000).unref();
      },
    };
  }
  ```

- **Wrapper process**. Launch the tool via a tiny Node supervisor that installs
  the watchdog and `child.kill()`s the tool when the session ends.

## Production safety

The watchdog is **development tooling**, not a production feature:

- Gate it on `process.env.NODE_ENV !== 'production'` (or Vite's `apply: 'serve'`).
- In production, **signal handling stays on** — orchestrators (Docker, K8s,
  systemd, PM2) stop processes with `SIGTERM`, and you still want the clean
  `server.close()` + `db.destroy()` path. Only the `ppid`/session watchdog is
  dev-only, since a production process legitimately running as PID 1's child
  would otherwise see `ppid === 1` and exit immediately.
- Keep `forceExitMs` so a hung connection or stuck cleanup can't wedge the
  process forever. It's a safety net — if you hit it routinely, fix the drain.

## Manual end-to-end check

Prove it against the real process tree. Start the stack, then **force-kill the
launcher** (`kill -9`) — the harshest case, since the launcher can't clean up —
and confirm the ports free themselves within ~1 second:

```bash
npm run dev &
sleep 6
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':3000|:3001'   # confirm ports held
kill -9 "$(pgrep -f 'concurrently')"                  # untrappable kill of launcher
for i in $(seq 1 8); do
  sleep 1
  lsof -nP -iTCP -sTCP:LISTEN | grep -qE ':3000|:3001' \
    && echo "t=${i}s: still held" \
    || { echo "t=${i}s: all ports released"; break; }
done
```

## Checklist

- [ ] Handle `SIGINT`, `SIGTERM`, **and `SIGHUP`**.
- [ ] `onShutdown` closes the server **and** the DB pool (and drains in-flight work).
- [ ] Shutdown is **idempotent** (a flag guards against double-run).
- [ ] A **`forceExitMs`** timeout guarantees the process eventually exits.
- [ ] Dev-only watchdog fires on `ppid === 1` **or** session-leader-gone.
- [ ] Launcher publishes its PID (`DEV_SESSION_PID=$$ exec …`).
- [ ] Watchdog is **disabled in production**; signal handling stays on.
- [ ] Third-party dev servers covered via a plugin hook or wrapper.
- [ ] Helper is unit-tested via injected seams; verified end-to-end with `kill -9`.

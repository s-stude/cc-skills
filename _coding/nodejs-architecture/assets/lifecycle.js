// Graceful shutdown + dev-only port-cleanup watchdog for long-lived Node
// processes (an HTTP server, a worker). Copy this file into the project and wire
// installGracefulShutdown() into each process with an onShutdown that closes the
// server and the DB pool. See references/graceful-shutdown.md.
//
// A long-lived process must be able to terminate itself — don't rely on a signal
// always arriving from above. Shutdown fires on ANY of three triggers:
//   1. a termination signal (SIGINT, SIGTERM, SIGHUP)
//   2. orphaned to init (process.ppid === 1)          [dev-only watchdog]
//   3. the dev session leader PID is gone             [dev-only watchdog]
//
// Everything external (process, timers, liveness check) is an injectable seam so
// the whole thing is unit-testable without actually killing the test runner.

const DEFAULT_SIGNALS = ['SIGINT', 'SIGTERM', 'SIGHUP'];

// A process is "alive" if kill(pid, 0) doesn't throw. EPERM means it exists but
// we can't signal it — still alive. ESRCH means it's gone.
function defaultIsAlive(pid, proc) {
  try {
    proc.kill(pid, 0);
    return true;
  } catch (error) {
    return error?.code === 'EPERM';
  }
}

// Read the dev session leader PID published by the launcher (DEV_SESSION_PID=$$).
// Returns undefined if unset or invalid, so callers can pass it through directly.
export function sessionPidFromEnv(env = process.env) {
  const pid = Number(env.DEV_SESSION_PID);
  return Number.isInteger(pid) && pid > 1 ? pid : undefined;
}

export function installGracefulShutdown({
  name = 'process',
  logger = console,
  onShutdown,
  watchOrphan = false,
  sessionPid,
  forceExitMs = 10_000,
  signals = DEFAULT_SIGNALS,
  // Injectable seams (defaults are the real runtime; tests pass fakes):
  proc = process,
  setIntervalFn = setInterval,
  clearIntervalFn = clearInterval,
  setTimeoutFn = setTimeout,
  isAlive = defaultIsAlive,
} = {}) {
  let shuttingDown = false;
  let watchdog;

  async function shutdown(reason) {
    if (shuttingDown) return; // idempotent — many triggers can race
    shuttingDown = true;

    logger.info?.(`[lifecycle] ${name} shutting down — ${reason}`);
    if (watchdog) clearIntervalFn(watchdog);

    // Safety net: if cleanup hangs, force the process out so it can't wedge.
    const forceTimer = setTimeoutFn(() => {
      logger.error?.(`[lifecycle] ${name} force exit after ${forceExitMs}ms`);
      proc.exit(1);
    }, forceExitMs);
    forceTimer?.unref?.();

    try {
      await onShutdown?.();
      logger.info?.(`[lifecycle] ${name} shutdown complete`);
      proc.exit(0);
    } catch (error) {
      logger.error?.(`[lifecycle] ${name} shutdown failed`, { error: error?.message });
      proc.exit(1);
    }
  }

  for (const signal of signals) {
    proc.on(signal, () => shutdown(`signal ${signal}`));
  }

  // Triggers 2 and 3 are development-only. In production ppid === 1 can be
  // legitimate (PID 1's direct child in a container), so the caller gates this.
  if (watchOrphan) {
    watchdog = setIntervalFn(() => {
      if (proc.ppid === 1) {
        shutdown('orphaned (ppid=1)');
        return;
      }
      if (sessionPid && !isAlive(sessionPid, proc)) {
        shutdown(`session leader ${sessionPid} gone`);
      }
    }, 1000);
    watchdog?.unref?.();
  }

  return {
    shutdown,
    isShuttingDown: () => shuttingDown,
  };
}

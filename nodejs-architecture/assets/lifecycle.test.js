import { describe, it, expect, vi } from 'vitest';
import { installGracefulShutdown, sessionPidFromEnv } from './lifecycle.js';

// A fake process: records signal handlers, captures exit codes instead of
// actually exiting, and lets tests set ppid / control kill().
function makeProc({ ppid = 1000, alivePids = new Set() } = {}) {
  const handlers = new Map();
  return {
    ppid,
    exit: vi.fn(),
    on(signal, fn) {
      handlers.set(signal, fn);
    },
    emit(signal) {
      handlers.get(signal)?.();
    },
    kill(pid, sig) {
      if (sig === 0 && !alivePids.has(pid)) {
        const err = new Error('ESRCH');
        err.code = 'ESRCH';
        throw err;
      }
    },
    handlers,
  };
}

// Capture interval/timeout callbacks so tests can fire them on demand.
function makeTimers() {
  const intervals = [];
  const timeouts = [];
  return {
    intervals,
    timeouts,
    setIntervalFn: (fn) => {
      intervals.push(fn);
      return { unref() {} };
    },
    clearIntervalFn: vi.fn(),
    setTimeoutFn: (fn) => {
      timeouts.push(fn);
      return { unref() {} };
    },
  };
}

const silentLogger = { info: vi.fn(), warn: vi.fn(), error: vi.fn() };

describe('sessionPidFromEnv', () => {
  it('parses a valid PID', () => {
    expect(sessionPidFromEnv({ DEV_SESSION_PID: '4242' })).toBe(4242);
  });

  it('rejects missing, non-numeric, and <= 1 values', () => {
    expect(sessionPidFromEnv({})).toBeUndefined();
    expect(sessionPidFromEnv({ DEV_SESSION_PID: 'nope' })).toBeUndefined();
    expect(sessionPidFromEnv({ DEV_SESSION_PID: '1' })).toBeUndefined();
    expect(sessionPidFromEnv({ DEV_SESSION_PID: '0' })).toBeUndefined();
  });
});

describe('installGracefulShutdown', () => {
  it('registers handlers for SIGINT, SIGTERM, and SIGHUP', () => {
    const proc = makeProc();
    const timers = makeTimers();
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, onShutdown: async () => {} });

    expect([...proc.handlers.keys()]).toEqual(['SIGINT', 'SIGTERM', 'SIGHUP']);
  });

  it('runs onShutdown and exits 0 on a signal', async () => {
    const proc = makeProc();
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {});
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, onShutdown });

    proc.emit('SIGTERM');
    await vi.waitFor(() => expect(proc.exit).toHaveBeenCalledWith(0));
    expect(onShutdown).toHaveBeenCalledTimes(1);
  });

  it('is idempotent — many triggers run onShutdown once', async () => {
    const proc = makeProc();
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {});
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, onShutdown });

    proc.emit('SIGINT');
    proc.emit('SIGTERM');
    proc.emit('SIGHUP');
    await vi.waitFor(() => expect(proc.exit).toHaveBeenCalled());
    expect(onShutdown).toHaveBeenCalledTimes(1);
  });

  it('exits 1 when onShutdown throws', async () => {
    const proc = makeProc();
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {
      throw new Error('cleanup boom');
    });
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, onShutdown });

    proc.emit('SIGTERM');
    await vi.waitFor(() => expect(proc.exit).toHaveBeenCalledWith(1));
  });

  it('force-exits when cleanup hangs past forceExitMs', async () => {
    const proc = makeProc();
    const timers = makeTimers();
    // onShutdown never resolves — the force timer must fire.
    installGracefulShutdown({
      logger: silentLogger,
      proc,
      ...timers,
      forceExitMs: 5,
      onShutdown: () => new Promise(() => {}),
    });

    proc.emit('SIGTERM');
    expect(timers.timeouts).toHaveLength(1);
    timers.timeouts[0](); // simulate the timeout firing
    expect(proc.exit).toHaveBeenCalledWith(1);
  });

  it('does not install a watchdog unless watchOrphan is set', () => {
    const proc = makeProc();
    const timers = makeTimers();
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, onShutdown: async () => {} });
    expect(timers.intervals).toHaveLength(0);
  });

  it('watchdog shuts down when orphaned (ppid === 1)', async () => {
    const proc = makeProc({ ppid: 1 });
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {});
    installGracefulShutdown({ logger: silentLogger, proc, ...timers, watchOrphan: true, onShutdown });

    timers.intervals[0](); // one watchdog tick
    await vi.waitFor(() => expect(onShutdown).toHaveBeenCalledTimes(1));
    expect(proc.exit).toHaveBeenCalledWith(0);
  });

  it('watchdog shuts down when the session leader PID is gone', async () => {
    const proc = makeProc({ ppid: 1000, alivePids: new Set() }); // 4242 not alive
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {});
    installGracefulShutdown({
      logger: silentLogger,
      proc,
      ...timers,
      watchOrphan: true,
      sessionPid: 4242,
      onShutdown,
    });

    timers.intervals[0]();
    await vi.waitFor(() => expect(onShutdown).toHaveBeenCalledTimes(1));
  });

  it('watchdog stays quiet while parent and session leader are alive', () => {
    const proc = makeProc({ ppid: 1000, alivePids: new Set([4242]) });
    const timers = makeTimers();
    const onShutdown = vi.fn(async () => {});
    installGracefulShutdown({
      logger: silentLogger,
      proc,
      ...timers,
      watchOrphan: true,
      sessionPid: 4242,
      onShutdown,
    });

    timers.intervals[0]();
    expect(onShutdown).not.toHaveBeenCalled();
    expect(proc.exit).not.toHaveBeenCalled();
  });
});

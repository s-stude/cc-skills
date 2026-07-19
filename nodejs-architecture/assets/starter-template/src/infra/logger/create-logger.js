// Winston logger normalized to the app's socket: info/warn/error(message, meta).
// The whole app depends on this shape, not on Winston. In a fuller setup an
// AsyncLocalStorage format stamps a traceId onto every line — see
// references/logging.md and references/cross-cutting.md.

import winston from 'winston';

export function createLogger({ level = 'info' } = {}) {
  const log = winston.createLogger({
    level,
    format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
    transports: [new winston.transports.Console()],
  });

  return {
    info: (message, meta) => log.info(message, meta ?? {}),
    warn: (message, meta) => log.warn(message, meta ?? {}),
    error: (message, meta) => log.error(message, meta ?? {}),
  };
}

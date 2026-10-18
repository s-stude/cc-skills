// Builds the Express app, plugs cross-cutting middleware, runs every plugin's
// register(), and installs the global error handler last. Returns the pieces the
// entry point needs to listen and shut down cleanly.

import express from 'express';
import { createContainer } from './container.js';

export async function createServer() {
  const app = express();
  app.use(express.json());

  const container = createContainer({ app });
  const { logger } = container;

  // Cross-cutting: HTTP request logging, plugged once, before routes.
  app.use((req, res, next) => {
    const startedAt = Date.now();
    res.on('finish', () => {
      logger.info('HTTP request completed', {
        method: req.method,
        path: req.path,
        statusCode: res.statusCode,
        durationMs: Date.now() - startedAt,
      });
    });
    next();
  });

  // Collect interfaces returned by plugins so required cross-module calls can
  // be injected. Optional reactions go through the event bus instead.
  const services = {};
  const context = { ...container, services };

  for (const plugin of container.plugins) {
    logger.info('Registering plugin', { plugin: plugin.name });
    const exposed = await plugin.register(context);
    if (exposed && typeof exposed === 'object') Object.assign(services, exposed);
  }

  // Global error handler, plugged last so it catches everything above.
  // Never silently swallow — log, then shape a safe response. Client errors
  // (bad input) are 400s, not 500s.
  app.use((error, req, res, _next) => {
    if (error.name === 'ZodError') {
      return res.status(400).json({ error: 'Invalid request' });
    }
    logger.error('Unhandled request error', {
      method: req.method,
      path: req.path,
      error: error.message,
    });
    res.status(error.statusCode ?? 500).json({ error: 'Internal server error' });
  });

  return { app, db: container.db, logger };
}

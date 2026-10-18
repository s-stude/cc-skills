// The wiring harness: build shared infra from the validated `env`, declare the
// ordered plugin list. Explicit construction, explicit order — no filesystem
// auto-discovery. The container consumes `env`; it never reads process.env.

import { env } from '../infra/config/env.js';
import { createLogger } from '../infra/logger/create-logger.js';
import { createEventBus } from '../infra/events/create-event-bus.js';
import { createSessions } from '../infra/auth/sessions.js';
import { createRequireAuth } from '../infra/auth/require-auth.js';

import { ordersPlugin } from '../modules/orders/index.js';
import { notificationsPlugin } from '../modules/notifications/index.js';

export function createContainer({ app }) {
  const logger = createLogger({ level: env.LOG_LEVEL });
  const eventBus = createEventBus({ logger });

  // In a real app this is a Knex instance (createDb({ env, logger })). The
  // starter uses an in-memory store so it runs with no database.
  const db = { orders: [] };

  const sessions = createSessions({ db });
  const requireAuth = createRequireAuth({ sessions, logger });

  return {
    app,
    env,
    logger,
    eventBus,
    db,
    requireAuth,
    plugins: [ordersPlugin, notificationsPlugin],
  };
}

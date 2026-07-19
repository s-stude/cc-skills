# Wiring — dependency injection without a framework

The wiring harness is the part of the car that already ran the wires, so no
component has to find the battery itself. In code: **dependencies are handed to a
module, never reached for.**

Stack for everything here: **plain JavaScript (ESM) + Express.js**. No
TypeScript, no DI framework. For simple and even medium apps you do **not** need
Awilix — a factory-function convention plus one container file is enough, and it
stays debuggable. A ready-to-copy custom DI container ships at
`assets/di/container.js` (documented at the end of this file).

## The one pattern: factory functions that take deps

Every service, repository, and adapter is a function that receives its
dependencies as a single `deps` object and returns the thing.

```js
// Bad — hardwired to Telegram, the DB, and a logger singleton.
import { sendTelegramMessage } from '../telegram/sendTelegramMessage.js';
import { db } from '../db.js';
import { logger } from '../logger.js';

export async function createOrder(input) {
  const order = await db.orders.insert(input);
  await sendTelegramMessage('Order created');
  logger.info('Order created');
  return order;
}
```

```js
// Good — dependencies are injected; nothing is imported that isn't a factory.
export function createOrderService({ orderRepository, eventBus, logger }) {
  return {
    async createOrder(input) {
      const order = await orderRepository.create(input);
      logger.info('Order created', { orderId: order.id });
      await eventBus.publish('order.created', {
        orderId: order.id,
        customerId: order.customerId,
      });
      return order;
    },
  };
}
```

Why this is enough: the "container" is just the one file where you call these
factories in the right order and pass the results along. That file *is* your
wiring harness — reading it top to bottom tells you the entire dependency graph.

## The plugin contract

A plugin is a feature that registers itself given a shared context. Keep it tiny.

A plugin is just an object with a `name` and a `register(context)` function:

```js
// A plugin registers routes, event subscribers, jobs, and/or middleware, and
// may return public interfaces (e.g. a service) for the container to share:
//
//   { name: string,
//     register(context) -> void | object | Promise<void | object> }
//
// The context is the standard wiring every plugin receives — the "harness":
//   { app, db, config, logger, eventBus, services }
```

## The container — infra + config in one place

The container builds shared infrastructure (logger, event bus, db, config) and
declares the ordered plugin list. Nothing magical: explicit construction,
explicit order.

```js
// app/container.js
import { env } from '../infra/config/env.js';
import { createLogger } from '../infra/logger/create-logger.js';
import { createEventBus } from '../infra/events/create-event-bus.js';
import { createDb } from '../infra/db/create-db.js';
import { createRequireAuth } from '../infra/auth/require-auth.js';
import { createSessions } from '../infra/auth/sessions.js';

import { ordersPlugin } from '../modules/orders/index.js';
import { customersPlugin } from '../modules/customers/index.js';
import { notificationsPlugin } from '../modules/notifications/index.js';
import { auditPlugin } from '../modules/audit/index.js';

export function createContainer({ app }) {
  // Config is read + validated ONCE in the env module, not here.
  // The container consumes `env`; it never touches process.env.
  const logger = createLogger({ level: env.LOG_LEVEL });
  const eventBus = createEventBus({ logger });
  const db = createDb({ env, logger }); // Knex instance
  const sessions = createSessions({ db });
  const requireAuth = createRequireAuth({ sessions, logger });

  return {
    app,
    env,
    logger,
    eventBus,
    db,
    requireAuth, // shared session middleware handed to every plugin
    // Explicit, ordered — never auto-discovered from the filesystem.
    // Order matters when one plugin's register() returns a service a later
    // plugin needs.
    plugins: [
      ordersPlugin,
      customersPlugin,
      notificationsPlugin,
      auditPlugin,
    ],
  };
}
```

Config lives in one Zod-validated `env` module the container imports — the app
never scatters `process.env.*` reads. → `references/configuration.md`

## The server bootstrap

`server.js` builds the Express app, wires cross-cutting middleware, then runs
every plugin's `register()`. Plugins that return interfaces get collected into a
`services` registry so *required* cross-module calls can be injected.

```js
// app/server.js
import express from 'express';
import { createContainer } from './container.js';
import { createHttpLogger } from '../infra/logger/http-logger.js';
import { createErrorHandler } from '../infra/logger/error-handler.js';

export async function createServer() {
  const app = express();
  app.use(express.json());

  const container = createContainer({ app });
  const { logger } = container;

  // Cross-cutting concerns plugged ONCE, before routes.
  app.use(createHttpLogger({ logger }));

  // Collect interfaces returned by plugins for required cross-module calls.
  const services = {};
  const context = { ...container, services };

  for (const plugin of container.plugins) {
    logger.info('Registering plugin', { plugin: plugin.name });
    const exposed = await plugin.register(context);
    if (exposed && typeof exposed === 'object') {
      Object.assign(services, exposed); // e.g. { orderService, customerService }
    }
  }

  // Error handling plugged LAST so it catches everything above.
  app.use(createErrorHandler({ logger }));

  // Return the pieces the entry point needs to listen + shut down cleanly.
  return { app, db: container.db, logger };
}
```

```js
// app/index.js — the process entry point
import { createServer } from './server.js';
import { env } from '../infra/config/env.js';
import { installGracefulShutdown, sessionPidFromEnv } from '../infra/lifecycle.js';

const { app, db, logger } = await createServer();
const server = app.listen(env.PORT, () => logger.info(`listening on ${env.PORT}`));

// Release the port + close the Knex pool on any exit. → references/graceful-shutdown.md
const isDev = env.NODE_ENV !== 'production';
installGracefulShutdown({
  name: 'API server',
  logger,
  watchOrphan: isDev,
  sessionPid: isDev ? sessionPidFromEnv() : undefined,
  onShutdown: async () => {
    await new Promise((resolve) => server.close(resolve));
    await db.destroy();
  },
});
```

## Required cross-module calls (when an event won't do)

Events are for optional reactions. When module A *requires* a synchronous result
from module B (e.g. billing must read the order total and the operation must fail
if it can't), inject B's service interface — do not import B's internals.

Two clean ways:

1. **Two-phase registration.** Plugins that only *build* services register first
   and return their interface; plugins that *consume* them read from
   `context.services` in their `register()`. Order the plugin list accordingly.
2. **A service in the container.** For a couple of always-needed services,
   construct them in `container.js` and pass them in the context.

Either way the consumer depends on the *interface shape* (the object's methods),
never on the file that implements it.

## Bundled custom DI container (`assets/di/container.js`)

For simple apps, a 40-line registry beats a framework. It supports:

- `register(name, factory)` — lazy singleton; the factory receives the container
  so it can resolve its own deps.
- `resolve(name)` — build once, cache, detect cycles.
- `value(name, obj)` — register an already-built instance (config, db handle).

Copy it and register your factories:

```js
import { createContainer } from './assets/di/container.js';
import { env } from './infra/config/env.js';

const c = createContainer();
c.value('env', env);
c.register('logger', (c) => createLogger({ level: c.resolve('env').LOG_LEVEL }));
c.register('eventBus', (c) => createEventBus({ logger: c.resolve('logger') }));
c.register('db', (c) => createDb({ env: c.resolve('env'), logger: c.resolve('logger') }));
c.register('orderRepository', (c) => createOrderRepository({ db: c.resolve('db') }));
c.register('orderService', (c) => createOrderService({
  orderRepository: c.resolve('orderRepository'),
  eventBus: c.resolve('eventBus'),
  logger: c.resolve('logger'),
}));

const orderService = c.resolve('orderService'); // whole graph built lazily
```

Reach for Awilix only if this registry starts hurting (scoped/per-request
lifetimes, hundreds of registrations). Most apps never get there.

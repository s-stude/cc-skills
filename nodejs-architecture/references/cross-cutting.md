# Cross-cutting concerns — infrastructure, not sprinkles

Logging, tracing, metrics, auth, validation, notifications, auditing — these cut
across every feature. The mistake is copying them into every function. The fix is
to plug them **once**, at the right layer.

Plain **JavaScript (ESM) + Express** throughout; the logger is **Winston**.

For *what* and *when* to log (the five categories, the should-I-log framework,
trace-ID propagation, redaction), see `references/logging.md`. This file is about
*where* each concern is wired.

## Where each concern lives

| Concern              | Home                                        |
| -------------------- | ------------------------------------------- |
| HTTP request logging | Express middleware                          |
| Error logging        | Global error handler                        |
| Trace-ID propagation | AsyncLocalStorage, seeded in middleware → `references/logging.md` |
| Tracing (spans)      | Middleware / OpenTelemetry instrumentation  |
| Metrics              | Middleware + event subscribers              |
| Notifications        | Event subscribers                           |
| Auditing             | Event subscribers                           |
| Validation           | Route boundary (Zod)                        |
| Auth (session → identity) | Middleware                             |
| Org scoping          | Service (verify) + repository (filter) → `references/security-tenancy.md` |
| Config               | One Zod-validated `env` module → `references/configuration.md` |
| Business rules       | Domain service                              |
| DB access            | Repository (Knex)                           |
| External APIs        | Adapter                                     |

The smell to hunt down when refactoring:

```js
// BAD — cross-cutting calls hand-copied into every function.
logger.info(...);
startTrace(...);
checkPermission(...);
validateInput(...);
recordMetric(...);
// ...actual business logic buried at the bottom
```

## Logging has three natural homes

Do not treat logging as one thing dumped everywhere. It splits cleanly:

### 1. Technical HTTP logging → middleware

```js
// infra/logger/http-logger.js
export function createHttpLogger({ logger }) {
  return function httpLogger(req, res, next) {
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
  };
}
```

```js
app.use(createHttpLogger({ logger })); // every route logged, once.
```

### 2. Business milestone logging → inside services

```js
logger.info('Order created', { orderId: order.id });
```

Sparing and meaningful — the handful of domain moments worth a line, not every
statement.

### 3. Error logging → global error handler (plugged last)

```js
// infra/logger/error-handler.js
export function createErrorHandler({ logger }) {
  // 4-arg signature — Express treats this as the error handler.
  return function errorHandler(error, req, res, next) {
    logger.error('Unhandled request error', {
      method: req.method,
      path: req.path,
      error: error.message,
      stack: error.stack,
    });
    res.status(error.statusCode ?? 500).json({ error: 'Internal server error' });
  };
}
```

Register it **after** all routes in `server.js` so it catches everything above.
This is also *the* rule for errors everywhere: **never silently swallow them.**
Let them propagate to a handler that logs and responds, or log-and-rethrow — an
empty `catch {}` hides real failures. (The event bus is the one deliberate
exception: it logs a failing subscriber *by name* and isolates it, because event
reactions are optional — required behavior stays a direct call so it fails loudly.
→ `references/events.md`)

## Logging ≠ notifications

The single most important distinction in this whole skill:

```txt
Logging      = technical observability (for engineers)
Notification = a business action (tell a human something)
```

```js
// BAD — a log line masquerading as a business workflow.
logger.info('ORDER_CREATED_SEND_TELEGRAM');

// GOOD — a domain event; subscribers decide what to do.
await eventBus.publish('order.created', payload);
// one subscriber logs it; a DIFFERENT subscriber sends Telegram.
```

If you ever want a critical log (e.g. `error`) to also ping a channel, do it as a
**Winston transport** that forwards `error`-level logs, kept dumb — it only
transports. Business notifications still go through events, never through the
logger.

## The logger itself is just a socket

Any implementation that satisfies `info/warn/error(message, meta)` fits. The
project default is **Winston**; the app only depends on the shape, and a
`traceId` is stamped onto every line by an AsyncLocalStorage format (→
`references/logging.md`).

```js
// infra/logger/create-logger.js
import winston from 'winston';
import { asyncContext } from './async-context.js';

// Pull traceId/requestId/userId from AsyncLocalStorage into every line.
const injectContext = winston.format((info) => {
  const store = asyncContext.getStore();
  if (store?.traceId) info.traceId = store.traceId;
  if (store?.requestId) info.requestId = store.requestId;
  if (store?.userId) info.userId = store.userId;
  return info;
});

export function createLogger({ level = 'info' } = {}) {
  const log = winston.createLogger({
    level,
    format: winston.format.combine(injectContext(), winston.format.json()),
    transports: [new winston.transports.Console()],
  });
  // Normalize to the app's socket: (message, meta) everywhere.
  return {
    info: (message, meta) => log.info(message, meta ?? {}),
    warn: (message, meta) => log.warn(message, meta ?? {}),
    error: (message, meta) => log.error(message, meta ?? {}),
  };
}
```

## Tracing → middleware + instrumentation

Don't have every module manage spans. Start a span at the HTTP boundary; let DB
and external-API adapters add spans; let services add a domain span only when
it's genuinely useful.

```js
// infra/tracing/create-tracing-middleware.js
export function createTracingMiddleware({ tracer }) {
  return function tracingMiddleware(req, res, next) {
    const span = tracer.startSpan(`${req.method} ${req.path}`);
    res.on('finish', () => {
      span.setAttribute('http.status_code', res.statusCode);
      span.end();
    });
    next();
  };
}
```

```js
app.use(createTracingMiddleware({ tracer }));
```

## Metrics, auditing, notifications → event subscribers

Anything that observes or reacts to *business* events belongs on the event bus,
not inline. Metrics can straddle: request-rate/latency in middleware, business
counters (`orders_created_total`) as subscribers.

```js
// modules/audit/audit.subscribers.js
import { ORDER_EVENTS } from '../orders/index.js';

export function registerAuditSubscribers({ eventBus, auditRepository }) {
  eventBus.subscribe(
    ORDER_EVENTS.CREATED,
    async (event) => auditRepository.record('order.created', event),
    { name: 'audit.onOrderCreated' },
  );
}
```

## Validation → the route boundary

Validate untrusted input where it enters (the route) with Zod, then hand clean
data plus the session-derived actor to the service. **No business logic in the
route** — it validates and delegates. Identity comes from `req.auth`, never from
the body.

```js
// modules/orders/order.routes.js
import express from 'express';
import { z } from 'zod';

const createOrderSchema = z.object({
  customerId: z.string(),
  items: z.array(z.object({ sku: z.string(), qty: z.number().int().positive() })),
});

export function createOrderRoutes({ orderService }) {
  const router = express.Router();
  router.post('/', async (req, res, next) => {
    try {
      const input = createOrderSchema.parse(req.body); // throws → error handler
      const order = await orderService.createOrder(req.auth, input); // actor from session
      res.status(201).json(order);
    } catch (error) {
      next(error);
    }
  });
  return router;
}
```

## Auth → session middleware

Authentication is middleware — it turns the **server-side session** into
`req.auth = { userId, orgId, role }` before any route runs. Identity is never
read from the body, query, or params. Coarse authorization (is there a session?
does the role gate this route?) lives here; per-entity authorization and org
scoping live in the service. Full patterns → `references/security-tenancy.md`.

```js
// infra/auth/require-auth.js
export function createRequireAuth({ sessions, logger }) {
  return async function requireAuth(req, res, next) {
    try {
      const session = await sessions.get(req); // server-side session store
      if (!session) return res.status(401).json({ error: 'Unauthorized' });
      // Identity comes from the SESSION, not the request payload.
      req.auth = { userId: session.userId, orgId: session.orgId, role: session.role };
      next();
    } catch (error) {
      logger.warn('Auth failed', { path: req.path });
      res.status(401).json({ error: 'Unauthorized' });
    }
  };
}
```

```js
app.use('/orders', createRequireAuth({ sessions, logger }), createOrderRoutes({ orderService }));
```

The throughline: **plug each concern once, at the layer that owns it.** Business
services should read like business logic (plus their access checks), not like a
checklist of infrastructure calls.

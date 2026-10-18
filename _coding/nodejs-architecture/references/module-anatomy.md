# Module anatomy — the replaceable part

A feature module is a **unit you can open, understand, and unplug**. Everything a
feature needs lives in one folder; everything others may touch is re-exported
from one `index.js`.

All code here is plain **JavaScript (ESM)**. No TypeScript and no JSDoc
annotation comments. A module's contract — its "socket" — is expressed by the
factory signature (the deps it destructures, the object it returns) and, where it
genuinely helps a reader, a single plain comment naming the expected methods.

## Folder layout

Files are **kebab-case**; module files follow `<name>.<role>.js`.

```txt
modules/orders/
  index.js              # PUBLIC SOCKET: the plugin + any allowed exports
  order.routes.js       # HTTP adapter (Express router)
  order.controller.js   # request→service→response glue (optional; fold into routes if thin)
  order.service.js      # business logic + access checks — depends on ports
  order.repository.js    # persistence adapter (Knex; every query org-scoped)
  order.events.js        # event name constants + payload shapes (as plain comments)
  order.subscribers.js   # this module's reactions to OTHER modules' events
  order.validation.js    # INTERNAL (Zod schemas) — not exported from index.js
```

A multi-word feature or helper uses kebab-case throughout —
`user-profile.repository.js`, `telegram-notifier.js`, `create-event-bus.js`.

File-name roles, at a glance:

```txt
index.js          the public plug — the only import path other modules may use
*.routes.js       HTTP adapter
*.service.js      business logic
*.repository.js   persistence adapter
*.subscribers.js  reactions to events
*.events.js       event names + payload shapes this module owns
```

## The `index.js` socket

Others import from here and nowhere else. Anything not re-exported is private by
construction — this is how JavaScript modules get real encapsulation without
`private` keywords.

```js
// modules/orders/index.js
import { createOrderRoutes } from './order.routes.js';
import { createOrderService } from './order.service.js';
import { createOrderRepository } from './order.repository.js';
import { ORDER_EVENTS } from './order.events.js';

// Event names are part of the public contract — other modules subscribe to them.
export { ORDER_EVENTS };

// The plugin is the primary export: the module registers itself.
export const ordersPlugin = {
  name: 'orders',
  register({ app, db, eventBus, logger, requireAuth }) {
    const orderRepository = createOrderRepository({ db });
    const orderService = createOrderService({ orderRepository, eventBus, logger });

    // requireAuth populates req.auth from the session before any route runs.
    app.use('/orders', requireAuth, createOrderRoutes({ orderService }));

    // If other modules need order data directly (required behavior),
    // expose the SERVICE INTERFACE here so the container can inject it.
    return { orderService };
  },
};
```

Good vs bad imports from the outside:

```js
// GOOD — depend on the socket
import { ordersPlugin, ORDER_EVENTS } from '../orders/index.js';

// BAD — reaching into internals; breaks the moment orders refactors
import { validateOrderInput } from '../orders/order.validation.js';
```

## Describing a port (the socket shape, no TypeScript, no JSDoc)

A "port" is the shape a dependency must satisfy. In plain JS you express it with
the code itself: a factory whose destructured deps name what it needs, plus a
one-line comment naming the contract when a reader would otherwise have to guess.

```js
// modules/notifications/notification.port.js
//
// Notifier socket — every notifier must expose:
//   send({ to, subject, body }) -> Promise<void>
// Swap Telegram / Email / SMS / a fake test double, as long as it fits this.
```

The contract lives in the function signature — no annotations needed. Business
logic depends on the *port* (the injected object's shape), not on any concrete
notifier:

Every service method takes an `actor` — the identity derived from the session
(`{ userId, orgId, role }`), never from the client — and scopes its work to
`actor.orgId`. This is where access is verified. → `references/security-tenancy.md`

```js
// modules/orders/order.service.js
// deps: orderRepository (create/findByIdForOrg), eventBus (publish), logger (info/error)
export function createOrderService({ orderRepository, eventBus, logger }) {
  return {
    // actor = { userId, orgId, role } from the session; input is Zod-validated.
    async createOrder(actor, input) {
      // Required behavior → direct, awaited call. org_id comes from the session,
      // so an order can never be created into another org.
      const order = await orderRepository.create(actor.orgId, input);

      logger.info('Order created', { orderId: order.id, orgId: actor.orgId });

      // Optional reactions → publish and move on.
      await eventBus.publish('order.created', {
        orderId: order.id,
        orgId: order.orgId,
        customerId: order.customerId,
        total: order.total,
      });

      return order;
    },
  };
}
```

The service does not know whether notifications go out by Telegram, email, or not
at all. It only knows the socket: `eventBus.publish(...)`. It *does* own access
control — the repository is the second line of defense, not the first.

## The repository is an adapter

The repository converts between your domain and the database (Knex + PostgreSQL).
Keep query details here so the service never imports a DB client. Every method
takes `orgId` and filters by it plus `is_deleted = false` — defense in depth, so
even a service that forgot to check can't leak across orgs. IDs are app-side
short strings; DB fields are snake_case; DTOs going back out are camelCase. Full
conventions → `references/database.md`.

```js
// modules/orders/order.repository.js
import { generateShortUID } from '../../infra/id.js';

// OrderRepository socket (every method is org-scoped):
//   create(orgId, input)        -> Promise<orderDto>
//   findByIdForOrg(orgId, id)   -> Promise<orderDto | null>
export function createOrderRepository({ db }) {
  const toDto = (row) => ({
    id: row.id,
    orgId: row.org_id,
    customerId: row.customer_id,
    total: row.total,
  });

  return {
    async create(orgId, input, trx) {
      const [row] = await (trx ?? db)('orders')
        .insert({
          id: generateShortUID(),
          org_id: orgId,
          customer_id: input.customerId,
          total: input.total,
        })
        .returning(['id', 'org_id', 'customer_id', 'total']);
      return toDto(row);
    },

    async findByIdForOrg(orgId, id) {
      const row = await db('orders')
        .where({ id, org_id: orgId, is_deleted: false })
        .first(['id', 'org_id', 'customer_id', 'total']);
      return row ? toDto(row) : null;
    },
  };
}
```

Swap Postgres for an in-memory fake in tests by passing a different object that
satisfies this socket — the service is none the wiser. That injectability is what
makes services testable without a database. → `references/testing.md`

## The routes file is the HTTP adapter

Keep HTTP concerns (status codes, request parsing) at this boundary; validate
untrusted input with Zod, pass the session-derived `req.auth` as the actor, and
let a global error handler deal with thrown errors. **No business logic here** —
the route delegates. Identity comes from `req.auth`, never from the body.

```js
// modules/orders/order.routes.js
import express from 'express';
import { z } from 'zod';

const createOrderSchema = z.object({
  customerId: z.string(),
  total: z.number().positive(),
});

export function createOrderRoutes({ orderService }) {
  const router = express.Router();

  router.post('/', async (req, res, next) => {
    try {
      const input = createOrderSchema.parse(req.body); // never trust it raw
      const order = await orderService.createOrder(req.auth, input); // actor from session
      res.status(201).json(order);
    } catch (error) {
      next(error); // global error handler logs + shapes the response
    }
  });

  return router;
}
```

`req.auth` is set by the session middleware (`require-auth`), which turns the
session cookie into `{ userId, orgId, role }`. → `references/security-tenancy.md`

## Events file — own your event names

Put the events a module *publishes* in one place so subscribers import stable
constants instead of magic strings.

```js
// modules/orders/order.events.js

export const ORDER_EVENTS = {
  CREATED: 'order.created',
  CANCELLED: 'order.cancelled',
};

// order.created payload: { orderId, orgId, customerId, total }
// Carry orgId in the payload so subscribers stay org-scoped too.
```

## Checklist for a well-formed module

For each module, you should be able to answer:

- **What is it?** (orders, customers, notifications, audit, billing…)
- **What does it expose?** (routes? a service interface? event subscribers? jobs?)
- **What does it need?** (db, logger, eventBus, config, an external API client)
- **What events does it publish?** (`order.created`, `order.cancelled`)
- **What events does it subscribe to?** (`payment.failed` → notify customer)

If those five answers are crisp, the boundaries are clean.

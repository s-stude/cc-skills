# Modular Node.js starter

The smallest runnable skeleton of the architecture: **Express + feature modules +
plugin registration + custom DI + in-memory event bus**, with the project's house
conventions wired in — **Zod-validated `env` config**, **Winston logging**,
**session-derived identity + org scoping**, `generateShortUID()` string IDs, and
**graceful shutdown**. Plain JavaScript (ESM, Node ≥ 20), no TypeScript.

The persistence layer is an in-memory store so it runs with no database; in a real
project the repository is Knex + PostgreSQL (see `references/database.md`).

## Run

```bash
cp .env.example .env
npm install
npm start

# create an order as org_a (identity comes from the session token, not the body):
curl -X POST localhost:3000/orders \
  -H 'authorization: Bearer demo-session-org-a' \
  -H 'content-type: application/json' \
  -d '{"customerId":"cust_1","total":42}'

# without a session token → 401:
curl -i -X POST localhost:3000/orders -H 'content-type: application/json' -d '{}'
```

You'll see the order created, `order.created` published, and the notifications
subscriber react — all without the orders module knowing notifications exist.

## Test

```bash
npm test
```

`order.service.test.js` shows the payoff of dependency injection: services are
tested by injecting plain fakes (no mocking framework), including a **cross-org
isolation** test. → `references/testing.md`

## What to look at

- `src/infra/config/env.js` — config read + validated once with Zod; fail fast.
- `src/infra/auth/` — server-side session → `req.auth` ({ userId, orgId, role }); identity never from the client.
- `src/app/container.js` — the wiring harness: shared infra + the ordered plugin list.
- `src/app/server.js` — builds Express, plugs middleware, runs each plugin's `register()`.
- `src/app/index.js` — listen + `installGracefulShutdown` (frees the port on any exit).
- `src/modules/orders/` — a full feature: socket, routes (validate + delegate), service (actor + access), org-scoped repository, events, and a test.
- `src/modules/notifications/` — a feature that only subscribes to events. Delete it
  from the plugin list in `container.js` and orders keep working.

## Add a feature

1. Create `src/modules/<feature>/` with an `index.js` exporting a plugin.
2. Build the service from injected deps in `register()`; every method takes the
   session `actor` and stays org-scoped. Mount routes behind `requireAuth`.
3. Add the plugin to the list in `container.js`.
4. Per interaction: required → direct call on an injected service interface;
   optional → publish/subscribe an event; durable/retriable → a job on the queue.

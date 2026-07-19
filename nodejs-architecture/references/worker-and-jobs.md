# Worker & async jobs — durable, retriable work

> Topic guide for the **nodejs-architecture** skill. Read this when a task needs
> to run **outside** the HTTP request — sending email, calling a slow external
> API, generating a report, syncing a third party — or asks about the worker, the
> job queue, retries, idempotency, or background processing.

The worker is a **separate Node process** that pulls from a **lease-based
PostgreSQL job queue**. The one rule that governs everything below:

> **A lease can expire and a job can run twice — so every handler must be
> idempotent and safe to retry.**

Plain **JavaScript (ESM)**. No TypeScript, no JSDoc. The worker shares the same
building blocks as the API — the custom DI container, the `env` module, the Knex
db, the Winston logger, and the feature-module services — so nothing here is a
parallel universe; it's the same app entered through a different door.

## Why a separate process (not inside the API)

Put background work in its own process, `src/worker/index.js`, not in an
`setInterval` inside the web server. The reasons are all about **isolation**:

- A job that pegs the CPU, leaks memory, or crashes can't take down HTTP request
  handling — the two processes fail independently.
- You **scale them independently** — run one API replica and five workers when
  the queue is deep, or the reverse.
- Long/slow work doesn't hold an Express event-loop tick hostage. HTTP stays
  responsive; the worker takes as long as it needs.

The worker reuses everything: it builds the **same container**, reads the **same
`env`** (→ `references/configuration.md`), opens the **same Knex pool**
(→ `references/database.md`), and constructs **feature-module services** the same
way the API's plugins do — it just wires them to a job loop instead of routes.

## Jobs vs. events — durable work vs. optional reactions

Don't confuse the in-process event bus (→ `references/events.md`) with the job
queue. They solve different problems:

| | In-process events | Durable jobs |
| --- | --- | --- |
| Lives in | the API process's memory | a Postgres `jobs` table |
| Survives a crash/restart? | **No** — lost with the process | **Yes** — the row is still there |
| Retried on failure? | No (logged and skipped) | Yes, with backoff, up to `max_attempts` |
| Use for | optional reactions (audit row, metric) | work that **must eventually happen** (charge a card, send an email) |

Rule of thumb: if losing the reaction on a restart is acceptable, publish an
**event**. If the work *must* happen even across a deploy or a crash, **enqueue a
job**. A subscriber may itself enqueue a job — that's the durable handoff.

## The lease-based PG job queue

One table. IDs are strings from `generateShortUID()` (→ `references/database.md`);
`org_id` travels **in the payload**, recorded server-side when the job is
enqueued — never trusted from a client later.

```txt
jobs
  id            text primary key        -- generateShortUID()
  org_id        text not null           -- server-side identity, recorded at enqueue
  type          text not null           -- e.g. 'order.send_receipt'
  payload       jsonb not null          -- everything the handler needs
  run_at        timestamptz not null    -- earliest time to run (backoff pushes this out)
  locked_until  timestamptz             -- the lease; null when claimable
  attempts      integer not null default 0
  max_attempts  integer not null default 5
  status        text not null default 'pending'  -- pending | done | failed
  created_at    timestamptz not null default now()
```

### Claiming a job atomically

A worker claims the next due job by selecting it **and** stamping a lease in one
statement. `FOR UPDATE SKIP LOCKED` is the load-bearing clause:

```js
// src/worker/claim.job.js
const LEASE_MS = 30_000;

export async function claimJob({ db }) {
  const [job] = await db.raw(
    `
    UPDATE jobs
    SET locked_until = now() + (?::int * interval '1 millisecond'),
        attempts = attempts + 1
    WHERE id = (
      SELECT id FROM jobs
      WHERE status = 'pending'
        AND run_at <= now()
        AND (locked_until IS NULL OR locked_until < now())
      ORDER BY run_at
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    RETURNING *
    `,
    [LEASE_MS],
  ).then((r) => r.rows);

  return job ?? null;
}
```

Why each piece matters:

- **`SKIP LOCKED`** — many workers poll the same table at once. Without it they'd
  block on the same row or double-claim it. `SKIP LOCKED` lets each worker grab a
  *different* row and move on, with no double-claim.
- **`locked_until` (the lease)** — the claim doesn't delete the row, it *leases*
  it for `LEASE_MS`. If the worker finishes, it marks the row `done`. If the
  worker **dies mid-job**, the lease simply expires and another worker re-claims
  the row on its next poll. That resilience is exactly **why a job can run
  twice** — which is why the next section is non-negotiable.

## Idempotency — the price of at-least-once delivery

Because a lease can expire and a job re-run, a handler that isn't idempotent will
double-charge a card or send two emails. Make every handler safe to run twice:

- **Natural idempotency key** — derive a stable key from the payload (e.g.
  `receipt:{orderId}`) and let a unique constraint or upsert absorb the second
  run.
- **"Already done?" check** — before any side effect, read whether the effect is
  already recorded, and short-circuit if so.
- **Record completion in the SAME transaction that does the work** — so the
  side-effect's *evidence* and the work commit together or not at all.

```js
// modules/orders/order.jobs.js
// deps: orderRepository (findById), receiptRepository (findByOrderId, create),
//       emailClient (send with timeout), logger
export function createSendReceiptHandler({ orderRepository, receiptRepository, emailClient, logger }) {
  return async function handleSendReceipt({ payload }) {
    const { orderId, orgId } = payload;

    // "Already done?" — a re-run after a lease expiry lands here and exits.
    const existing = await receiptRepository.findByOrderId({ orgId, orderId });
    if (existing) {
      logger.info('Receipt already sent, skipping', { orderId });
      return;
    }

    const order = await orderRepository.findById({ orgId, id: orderId });
    if (!order) throw new Error(`order ${orderId} not found`);

    const messageId = await emailClient.send({
      to: order.customerEmail,
      subject: `Receipt for order ${orderId}`,
    });

    // Completion recorded with a unique(org_id, order_id): a racing second run
    // hits the constraint and is treated as already-done.
    await receiptRepository.create({ orgId, orderId, messageId });
  };
}
```

Note `orgId` flows from the payload straight into every repository call — the
worker enforces tenancy exactly like a request actor does
(→ `references/security-tenancy.md`).

## Retry & backoff

On success, mark the row `done`. On failure, **don't swallow it** — log with
Winston at the right level, then either schedule a retry or dead-letter it:

```js
// src/worker/run.job.js
export async function runJob({ db, registry, logger }, job) {
  const handler = registry.get(job.type);
  if (!handler) {
    logger.error('No handler for job type', { type: job.type, jobId: job.id });
    await db('jobs').where({ id: job.id }).update({ status: 'failed', locked_until: null });
    return;
  }

  try {
    await handler({ payload: job.payload });
    await db('jobs').where({ id: job.id }).update({ status: 'done', locked_until: null });
  } catch (error) {
    if (job.attempts >= job.max_attempts) {
      // Dead-letter: stop retrying, leave it visible for inspection.
      logger.error('Job failed permanently', { jobId: job.id, type: job.type, error: error.message });
      await db('jobs').where({ id: job.id }).update({ status: 'failed', locked_until: null });
      return;
    }
    const backoffMs = Math.min(2 ** job.attempts * 1_000, 60_000); // exponential, capped
    logger.warn('Job failed, will retry', { jobId: job.id, attempt: job.attempts, backoffMs });
    await db('jobs')
      .where({ id: job.id })
      .update({ status: 'pending', locked_until: null, run_at: db.raw(`now() + (? * interval '1 millisecond')`, [backoffMs]) });
  }
}
```

`attempts` was already incremented at claim time, so it counts even a run that
crashed the worker before reaching this code — the lease expiry brings the row
back and the count keeps climbing toward `max_attempts`.

## Bounded concurrency

Run a **small pool** of in-flight jobs, not one-at-a-time and not unbounded. And
independently, bound concurrency on **external calls** so a burst of jobs can't
open 500 sockets to a provider. A tiny inline semaphore does the job — no
dependency unless a real need appears (→ `references/tooling.md`):

```js
// infra/concurrency/create-semaphore.js
export function createSemaphore(max) {
  let active = 0;
  const queue = [];
  const next = () => {
    if (active >= max || queue.length === 0) return;
    active += 1;
    queue.shift()();
  };
  return async function acquire() {
    await new Promise((resolve) => {
      queue.push(resolve);
      next();
    });
    return function release() {
      active -= 1;
      next();
    };
  };
}
```

The worker loop keeps `WORKER_CONCURRENCY` jobs in flight; a handler that fans out
to an external API wraps those calls in a second, tighter semaphore.

## Timeouts on ALL outbound requests

A hung dependency with no timeout wedges a worker slot forever, and enough of them
starve the whole pool. Every outbound request gets an `AbortController` timeout —
no exceptions:

```js
// infra/http/fetch-with-timeout.js
export async function fetchWithTimeout(url, options = {}, timeoutMs = 10_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer); // always clear, success or abort
  }
}
```

Wrap DB-external clients (email, payments, third-party APIs) so no code path can
skip the timeout. A slow provider then fails *this* job — which retries — instead
of silently holding a lease.

## Handlers are registered like plugins

The worker builds a **registry** mapping `type -> handler`, assembled from feature
modules exactly the way the API mounts plugins. A module contributes its jobs; the
worker composes them. This keeps the plugin idea intact across both processes:

```js
// src/worker/registry.js
export function createJobRegistry() {
  const handlers = new Map();
  return {
    register(type, handler) {
      if (handlers.has(type)) throw new Error(`duplicate job handler: ${type}`);
      handlers.set(type, handler);
    },
    get(type) {
      return handlers.get(type) ?? null;
    },
  };
}
```

```js
// src/worker/index.js (shape)
const container = createContainer({ env });
const registry = createJobRegistry();

// Each feature module contributes handlers, built from injected deps.
registry.register('order.send_receipt', createSendReceiptHandler(container.resolve('orders')));
// ...more modules

await runWorkerLoop({ db: container.resolve('db'), registry, logger });
```

## Enqueue API — insert a row (a transactional outbox)

Services enqueue by inserting a `jobs` row. The payoff: pass the **same `trx`**
that made the state change, so the job is enqueued **atomically with the work that
warrants it** — a transactional-outbox flavor. Either the order and its
"send receipt" job both commit, or neither does. No lost jobs, no orphan jobs.

```js
// infra/jobs/enqueue-job.js
import { generateShortUID } from '../id.js';

export function createEnqueueJob({ db }) {
  // enqueueJob({ type, payload, orgId, runAt }, trx?) — trx makes it outbox-safe
  return async function enqueueJob({ type, payload, orgId, runAt = new Date() }, trx = db) {
    const [row] = await trx('jobs')
      .insert({
        id: generateShortUID(),
        org_id: orgId,
        type,
        payload: JSON.stringify({ ...payload, orgId }),
        run_at: runAt,
      })
      .returning('id');
    return row.id;
  };
}
```

```js
// modules/orders/order.service.js (excerpt) — enqueue in the same trx as the write
await db.transaction(async (trx) => {
  const order = await orderRepository.create(input, trx);
  await enqueueJob({ type: 'order.send_receipt', payload: { orderId: order.id }, orgId: actor.orgId }, trx);
});
```

## Graceful shutdown

On `SIGTERM`/`SIGINT`/`SIGHUP` the worker must **stop claiming new jobs**, let the
**in-flight job finish** within a bounded wait, then **close the Knex pool** — in
that order, so a job is never abandoned mid-write and the lease is left clean for
the next worker. The worker wiring for this already lives in
→ `references/graceful-shutdown.md`; don't reinvent it here.

## Testing

Test **retry and idempotency** whenever you change worker behavior — run the same
handler twice and assert exactly one side effect; force a failure and assert the
row goes back to `pending` with a pushed-out `run_at`, then to `failed` after
`max_attempts`. **Never call paid external providers from tests** — inject a fake
email/payment client through the handler's deps. Full patterns:
→ `references/testing.md`.

## Checklist for a well-formed job

- **Idempotent?** Safe to run twice — an "already done?" check, a natural key, or
  completion recorded in the same transaction as the work.
- **Retry-safe?** Failure logs at the right level, increments `attempts`, backs
  off, and dead-letters at `max_attempts` — never silently swallowed.
- **Bounded?** The pool caps in-flight jobs; external calls have their own tighter
  concurrency bound.
- **Timed out?** Every outbound request uses an `AbortController` timeout.
- **Tenant-scoped?** `org_id` comes from the payload (recorded at enqueue) and is
  passed to every service/repository call.
- **Registered?** The handler is in the registry, contributed by its feature
  module like a plugin.
- **Enqueued atomically?** Where it matters, the job is inserted in the same `trx`
  as the state change that justifies it.

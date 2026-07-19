> Topic guide for the **nodejs-architecture** skill. Read this when you're adding
> or updating tests, deciding what a change actually needs covered, or wondering
> how to test without a mocking framework or a live external provider.

The payoff of the whole design shows up here. Because every service, repository,
and adapter is a **factory that takes its dependencies as an argument**
(→ `references/wiring.md`), you test by *handing it fakes*. A fake repository is
an object literal that satisfies the same socket. A fake notifier is an object
with the same `send(...)` method. An in-memory event bus records what was
published. No `jest.mock`, no module interception, no import juggling — you
construct the unit with the deps you want and assert on plain objects. Ports and
adapters plus dependency injection *are* the test strategy.

Tests use **Vitest**. All code here is plain JavaScript (ESM). Test files sit
next to what they test as `<name>.test.js`.

## Setup — minimal, no config

Basic ESM needs no Vitest config file. Two scripts in `package.json` are enough:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

`vitest run` executes once and exits (use it in CI and when you claim a pass);
`vitest` alone watches. Reach for a `vitest.config.js` only when a real need
appears — coverage thresholds, a setup file, path aliases. Don't add one
speculatively.

## Unit-testing a service by injecting fakes

Build the service with fakes that satisfy each socket. The fake repository is a
bare object; the in-memory bus records publishes; the logger is silent so test
output stays clean.

```js
// modules/orders/order.service.test.js
import { describe, it, expect } from 'vitest';
import { createOrderService } from './order.service.js';

const silentLogger = { info() {}, warn() {}, error() {} };

function makeInMemoryBus() {
  const published = [];
  return {
    published,
    async publish(event, payload) {
      published.push({ event, payload });
    },
  };
}

function makeFakeOrderRepository() {
  const rows = [];
  return {
    rows,
    async create(input) {
      const order = { id: `ord_${rows.length + 1}`, ...input };
      rows.push(order);
      return order;
    },
    async findById(id) {
      return rows.find((r) => r.id === id) ?? null;
    },
  };
}

describe('createOrderService.createOrder', () => {
  it('persists the order and publishes order.created', async () => {
    const orderRepository = makeFakeOrderRepository();
    const eventBus = makeInMemoryBus();
    const service = createOrderService({ orderRepository, eventBus, logger: silentLogger });

    const order = await service.createOrder({ customerId: 'cus_1', total: 4200 });

    expect(orderRepository.rows).toHaveLength(1);
    expect(eventBus.published).toEqual([
      { event: 'order.created', payload: { orderId: order.id, customerId: 'cus_1', total: 4200 } },
    ]);
  });
});
```

Nothing is mocked. The fakes are the injected deps. If you swap the real Knex
repository for `makeFakeOrderRepository()`, the service can't tell — that's the
socket doing its job.

A fake notifier that records calls is the same move for an outbound adapter:

```js
function makeFakeNotifier() {
  const sent = [];
  return {
    sent,
    async send({ to, subject, body }) {
      sent.push({ to, subject, body });
    },
  };
}
```

Assert `notifier.sent` to prove the right message went out — without touching a
real Telegram/email/SMS provider.

## Testing org scoping + authorization (required for sensitive changes)

Multi-tenancy is backend-enforced (→ `references/security-tenancy.md`), so any
change to a service that reads or mutates org data must prove cross-tenant access
is impossible. Two tests carry their weight:

```js
// modules/orders/order.service.authz.test.js
import { describe, it, expect } from 'vitest';
import { createOrderService } from './order.service.js';

const silentLogger = { info() {}, warn() {}, error() {} };

// A fake repo that scopes by org_id, exactly like the real Knex adapter must.
function makeScopedRepository(seed) {
  const rows = [...seed];
  return {
    async findById(id, { orgId }) {
      return rows.find((r) => r.id === id && r.orgId === orgId) ?? null;
    },
  };
}

describe('order access is org-scoped', () => {
  it('cannot read an order owned by another org', async () => {
    const orderRepository = makeScopedRepository([{ id: 'ord_1', orgId: 'org_b', total: 100 }]);
    const service = createOrderService({ orderRepository, eventBus: { publish() {} }, logger: silentLogger });

    const actor = { userId: 'usr_1', orgId: 'org_a', role: 'admin' };

    await expect(service.getOrder('ord_1', actor)).rejects.toThrow(/not found/i);
  });

  it('rejects an admin-only action from a member', async () => {
    const orderRepository = makeScopedRepository([{ id: 'ord_1', orgId: 'org_a', total: 100 }]);
    const service = createOrderService({ orderRepository, eventBus: { publish() {} }, logger: silentLogger });

    const member = { userId: 'usr_2', orgId: 'org_a', role: 'member' };

    await expect(service.cancelOrder('ord_1', member)).rejects.toThrow(/forbidden/i);
  });
});
```

The first test proves a cross-org read fails as if the row doesn't exist (a 404,
not a 403 — don't leak existence). The second proves authorization lives in the
service, not only in the UI. Test the *deny* path; a passing happy path proves
nothing about tenancy.

## Testing worker retry + idempotency (required when changing worker behavior)

Job handlers run at-least-once, so changing one means proving it's idempotent and
that failures retry (→ `references/worker-and-jobs.md`). Run the same job twice
and assert the side effect happened once; then force a failure and assert the
attempt count grew and a retry was scheduled.

```js
// worker/handlers/charge-order.test.js
import { describe, it, expect } from 'vitest';
import { createChargeOrderHandler } from './charge-order.js';

function makeFakePayments() {
  const charges = [];
  return {
    charges,
    async charge({ orderId, idempotencyKey }) {
      if (charges.some((c) => c.idempotencyKey === idempotencyKey)) return;
      charges.push({ orderId, idempotencyKey });
    },
  };
}

describe('charge-order handler', () => {
  it('is idempotent — running the same job twice charges once', async () => {
    const payments = makeFakePayments();
    const handle = createChargeOrderHandler({ payments });
    const job = { id: 'job_1', data: { orderId: 'ord_1', idempotencyKey: 'ord_1:charge' } };

    await handle(job);
    await handle(job);

    expect(payments.charges).toHaveLength(1);
  });

  it('increments attempts and schedules a retry on failure', async () => {
    const failingPayments = { async charge() { throw new Error('provider timeout'); } };
    const scheduled = [];
    const queue = { async scheduleRetry(job, delayMs) { scheduled.push({ job, delayMs }); } };
    const handle = createChargeOrderHandler({ payments: failingPayments, queue });
    const job = { id: 'job_2', attempts: 0, data: { orderId: 'ord_2', idempotencyKey: 'ord_2:charge' } };

    await handle(job);

    expect(job.attempts).toBe(1);
    expect(scheduled).toHaveLength(1);
  });
});
```

The idempotency key is what makes the double-run safe; the fake payments adapter
lets you assert it without a real charge.

## No paid external providers in tests

Never let a test hit a real payment, LLM, or email provider — it's slow, flaky,
and costs money. The socket makes avoiding it trivial: **inject a fake for every
external adapter**, exactly as the notifier and payments fakes above. If a test
seems to need the real provider, the seam is in the wrong place — push the
adapter behind a port and inject a double.

For database tests you have two honest options:

- **A fake repository** (object literal satisfying the repo socket). Fast, no DB,
  but you're testing the service's logic, not your SQL.
- **A real DB in a transaction rolled back per test.** Slower and needs a test
  database, but exercises real Knex queries and org-scoping SQL. Wrap each test
  in a `trx` and roll it back in an `afterEach` so tests don't leak state.

Use fakes for service logic and org-scope decisions; use a rolled-back
transaction when the query itself (the `where org_id` clause) is what you need to
prove.

## Honesty rule (hard)

Only claim a test or command passed if you actually ran it and read the output.
Run `npx vitest run` (or `npm test`), then trust the real result — paste it, don't
paraphrase from memory or assume green because the code "looks right." A
fabricated pass is worse than a known failure. This is not negotiable.

## When to reach for `vi`

`import { describe, it, expect, vi } from 'vitest'` is available, but prefer plain
fakes — they keep the DI point front and center and read more clearly. Use `vi`
narrowly for things injection can't reach: `vi.useFakeTimers()` for retry/backoff
delays, or `vi.fn()` when you want a call-count assertion on a one-method double.
Avoid `vi.mock()` of whole modules — if you feel you need it, a dependency is
being imported instead of injected; fix the seam instead.

## A worked example ships with the skill

`assets/lifecycle.js` comes with its own `assets/lifecycle.test.js`. It's a live
example of testing via **injected seams**: the process signal hooks and the exit
function are passed in as dependencies, so the test drives shutdown and asserts
the pool closed and exit was called — no real process is killed. Read it when you
need to test something that would otherwise touch global process state.
→ `references/graceful-shutdown.md`

## Checklist

- Test script is `vitest run`; `test:watch` is `vitest`. No config unless a real need appears.
- New/changed meaningful behavior has a test; test names describe behavior, not implementation.
- Services are tested by **injecting fakes** (object literals satisfying the socket) — no `vi.mock`.
- A fake for every external adapter; **no test hits a paid provider**.
- Sensitive backend change → a cross-org access test (expect 404) **and** a member-vs-admin authz test.
- Worker change → an idempotency test (run twice, effect once) **and** a retry-on-failure test.
- DB tests use a fake repo or a per-test rolled-back transaction — never shared mutable state.
- You ran `npx vitest run` and read the output before claiming anything passed.

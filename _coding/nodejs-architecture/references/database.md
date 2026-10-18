# Database conventions — the persistence adapter

> Topic guide for the **nodejs-architecture** skill. Read this when you're writing
> a repository, designing a table, choosing an ID scheme, scoping a query to an
> org, or deciding where a transaction belongs.

The repository is the **adapter behind a module's socket** (see
`references/module-anatomy.md`). It converts between your domain — camelCase DTOs,
string IDs — and PostgreSQL — snake_case columns, plural tables. Keep every Knex
detail here so the service never imports a DB client and never sees SQL. Stack:
**Knex + PostgreSQL**, string IDs generated app-side, Winston for logging.

## The house rules, and why

- **Field names are snake_case** in the database (`org_id`, `created_at`,
  `is_deleted`). DTO properties stay camelCase. The repository is the single
  place that translates — so the DB can stay idiomatic SQL while services and
  HTTP speak idiomatic JS.
- **Table names are plural** — `orders`, `users`, `organizations`, `subscribers`.
- **IDs are short string IDs from `generateShortUID()`**, not DB UUIDs or serial
  integers. App-side IDs are portable (they survive an export/import or a DB
  swap), client-safe (opaque, non-sequential — no row-count leak), and known
  *before* the insert, so you can publish an event or write a child row without a
  round-trip to read back a generated key.
- **Queries use async/await** and select columns explicitly when the caller
  needs a specific shape — don't lean on `select *` for anything crossing a
  boundary.
- **Soft deletes** use an `is_deleted` boolean; every read filters
  `is_deleted = false`. Rows are never physically removed on a normal delete.
- **Transactions are composed in the service layer.** Repositories accept an
  optional `trx` and otherwise use the base connection.
- **Every org-owned query is scoped by `org_id`**, and that `org_id` is a
  *required argument* the service passes in — derived from the session, never
  read from the client. This is the non-negotiable one. → `references/security-tenancy.md`

## generateShortUID — `src/infra/id.js`

A tiny base62 encoding of random bytes from `node:crypto`. No external
dependency — that's the point.

```js
// src/infra/id.js
import { randomBytes } from 'node:crypto';

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
const DEFAULT_LENGTH = 20;

export function generateShortUID(length = DEFAULT_LENGTH) {
  const bytes = randomBytes(length);
  let id = '';
  for (let i = 0; i < length; i += 1) {
    id += ALPHABET[bytes[i] % ALPHABET.length];
  }
  return id;
}
```

The app owns identity, so an order has its `id` the instant it's created —
before it touches the database.

## A realistic repository — `src/modules/orders/order.repository.js`

Note what the service must hand in: `db` (the Knex connection) and, on every
call that reads or writes org data, an `orgId`. The repository never reaches for
a global connection and never invents an `orgId`.

```js
// src/modules/orders/order.repository.js
//
// OrderRepository socket:
//   create({ orgId, customerId, total }, trx?) -> Promise<orderDto>
//   findById(orgId, id)                         -> Promise<orderDto | null>
//   listByOrg(orgId)                            -> Promise<orderDto[]>
//   softDelete(orgId, id, trx?)                 -> Promise<boolean>
import { generateShortUID } from '../../infra/id.js';

const TABLE = 'orders';
const COLUMNS = ['id', 'org_id', 'customer_id', 'total', 'status', 'created_at'];

function toDto(row) {
  if (!row) return null;
  return {
    id: row.id,
    orgId: row.org_id,
    customerId: row.customer_id,
    total: row.total,
    status: row.status,
    createdAt: row.created_at,
  };
}

export function createOrderRepository({ db }) {
  return {
    async create({ orgId, customerId, total }, trx) {
      const [row] = await (trx ?? db)(TABLE)
        .insert({
          id: generateShortUID(),
          org_id: orgId,
          customer_id: customerId,
          total,
          status: 'pending',
          is_deleted: false,
        })
        .returning(COLUMNS);
      return toDto(row);
    },

    async findById(orgId, id) {
      const row = await db(TABLE)
        .select(COLUMNS)
        .where({ id, org_id: orgId, is_deleted: false })
        .first();
      return toDto(row) ?? null;
    },

    async listByOrg(orgId) {
      const rows = await db(TABLE)
        .select(COLUMNS)
        .where({ org_id: orgId, is_deleted: false })
        .orderBy('created_at', 'desc');
      return rows.map(toDto);
    },

    async softDelete(orgId, id, trx) {
      const updated = await (trx ?? db)(TABLE)
        .where({ id, org_id: orgId, is_deleted: false })
        .update({ is_deleted: true });
      return updated > 0;
    },
  };
}
```

Every `where` carries both `org_id` and `is_deleted: false`. A missing `org_id`
filter is a cross-tenant leak, not a style nit — one org reading another's
orders. The `org_id` in these queries came from the service, which read it off
the session; it never arrived in `req.body`.

## The DTO boundary

DB rows are snake_case; DTOs are camelCase. Map once, at the repository edge, via
a `toDto` helper (above). Everything upstream — service, controller, HTTP JSON —
speaks camelCase and never sees `org_id` or `created_at`. This is the same
adapter idea as `references/module-anatomy.md`: the repository is the converter,
so the DB convention and the app convention never bleed into each other.

## Transactions live in the service

Repositories expose a `trx` param; they don't open transactions. The service
composes a unit of work — because only the service knows which writes must
succeed or fail together.

```js
// src/modules/orders/order.service.js
// deps: db (knex), orderRepository, customerRepository, eventBus, logger
export function createOrderService({ db, orderRepository, customerRepository, eventBus, logger }) {
  return {
    async placeOrder({ orgId, customerId, total }) {
      const order = await db.transaction(async (trx) => {
        const created = await orderRepository.create({ orgId, customerId, total }, trx);
        await customerRepository.incrementLifetimeValue(orgId, customerId, total, trx);
        return created;
      });

      logger.info('Order placed', { orderId: order.id });
      await eventBus.publish('order.created', { orgId, orderId: order.id, total });
      return order;
    },
  };
}
```

Both writes share one `trx`, so they commit or roll back together. Note the
`orgId` threaded into every repository call — required behavior stays a direct,
awaited call inside the transaction; optional reactions go out as an event after
it commits. → `references/module-anatomy.md`

## Migrations

Migrations are **additive** — never edit one that has already been applied; write
a new migration to change a shipped table. Tables are plural, IDs are string
primary keys, and org-owned tables carry `org_id` plus an `is_deleted` column
with an index (soft-delete filters and org scoping run on nearly every query).

```js
export async function up(knex) {
  await knex.schema.createTable('orders', (table) => {
    table.string('id').primary();
    table.string('org_id').notNullable();
    table.string('customer_id').notNullable();
    table.decimal('total', 12, 2).notNullable();
    table.string('status').notNullable().defaultTo('pending');
    table.boolean('is_deleted').notNullable().defaultTo(false);
    table.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    table.index(['org_id', 'is_deleted']);
  });
}

export async function down(knex) {
  await knex.schema.dropTable('orders');
}
```

## Related reading

- `references/module-anatomy.md` — the repository is the adapter behind a
  module's `index.js` socket.
- `references/security-tenancy.md` — why `org_id` comes from the session and how
  scoping is enforced everywhere.
- `references/worker-and-jobs.md` — the lease-based job queue is also a
  PostgreSQL table, with the same conventions.
- `references/configuration.md` — `DATABASE_URL` is read and validated once in
  the `env` module.

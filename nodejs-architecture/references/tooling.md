# Tooling — the stack, and when to add to it

> Topic guide for the **nodejs-architecture** skill. Read this when choosing a
> library, or deciding whether a new dependency is justified.

The stack is fixed and deliberately conservative: **plain JavaScript (ESM) on
Node ≥ 20**, **Express**, **Knex + PostgreSQL**, **Zod**, **Winston**,
**server-side sessions**, a **separate worker** draining a lease-based PostgreSQL
job queue, and **Vitest** for tests. DI and in-process events use a **custom
container + event bus** (bundled in `assets/`). Add heavier tools only when a
real pain shows up — every abstraction is one more thing to debug.

## The default stack

| Need                 | Use                                     | Notes / graduate to…                                |
| -------------------- | --------------------------------------- | --------------------------------------------------- |
| Runtime              | **Node.js ≥ 20**, ESM                   | never convert to TypeScript                         |
| HTTP framework       | **Express**                             | cross-cutting concerns live in middleware           |
| Persistence          | **Knex + PostgreSQL**                   | repository is the adapter → `references/database.md` |
| Validation           | **Zod**                                 | at route boundaries and for config                  |
| Config               | **dotenv + Zod**, one `env` module      | → `references/configuration.md`                     |
| Logging              | **Winston**                             | + AsyncLocalStorage trace IDs → `references/logging.md` |
| Auth                 | **server-side sessions**                | session → `{ userId, orgId, role }` → `references/security-tenancy.md` |
| IDs                  | **`generateShortUID()`**                | app-side string IDs, not DB UUIDs                   |
| Dependency injection | **custom container** (`assets/di/`)     | scoped lifetimes / 100s of registrations → Awilix   |
| In-process events    | **custom event bus** (`assets/pubsub/`) | cross-process/durable → the job queue below         |
| Async / background   | **worker + lease-based PG job queue**   | → `references/worker-and-jobs.md`; heavy fan-out → BullMQ |
| Tests                | **Vitest**                              | DI makes fakes trivial → `references/testing.md`    |
| Process lifecycle    | **`assets/lifecycle.js`**               | graceful shutdown → `references/graceful-shutdown.md` |
| Tracing              | none by default                         | distributed traces → OpenTelemetry                  |

## Why these defaults

- **Express** is unopinionated, so you build the plugin/DI/event structure this
  skill provides. Middleware is the natural home for cross-cutting concerns.
- **Knex over an ORM.** Explicit queries, explicit columns, an easy `trx` to
  thread through the service layer. The repository hides Knex behind a small
  socket, so the rest of the app never imports it. → `references/database.md`
- **Winston, not Pino, is the project default** — it satisfies the
  `info/warn/error(message, meta)` logger socket the app depends on, and pairs
  with AsyncLocalStorage to stamp every line with a trace ID.
- **Custom DI over Awilix.** For simple/medium apps the factory-function
  convention plus one `container.js` is the whole DI story and stays readable.
  Awilix earns its place only with per-request scopes or a very large graph.
- **Custom event bus for in-process reactions; the PG job queue for durable
  async.** Events are optional, in-memory, best-effort reactions; jobs are
  durable, retriable, cross-process work. Don't reach for RabbitMQ/Kafka until
  you actually need a broker. → `references/worker-and-jobs.md`, `references/events.md`
- **Zod** guards untrusted input at route boundaries and validates config once at
  startup so the process fails fast instead of booting half-configured.

## Rules of thumb for adding a tool

1. **Don't add a framework or dependency unless it's necessary.** Prefer
   extending an existing helper/service/repository over pulling in something new
   or duplicating what exists.
2. **Wait for the pain.** No BullMQ before you have fan-out the PG queue can't
   handle; no OpenTelemetry before you need distributed traces.
3. **Hide it behind a socket.** A new tool goes behind an interface (a factory, a
   `publish/subscribe` shape, a repository) so it can be swapped without touching
   business code.
4. **One place to wire it.** New infra is constructed in `container.js` and
   injected — never imported deep inside a service. Config it needs is a field on
   the `env` schema, not a fresh `process.env` read.

The goal is the sweet spot: *modular and replaceable, but not over-engineered.*

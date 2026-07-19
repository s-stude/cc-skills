---
name: nodejs-architecture
description: >-
  Design, structure, and refactor Node.js backend applications as modular,
  plug-and-play systems using feature modules, dependency injection, a plugin
  registry, domain events, and ports/adapters. Use this skill whenever the user
  is starting a new Node.js/Express service, organizing folders for a backend,
  deciding where code should live (routes, services, repositories, workers,
  notifications, logging, config), asking how to make features "pluggable" or
  "swappable", wiring dependencies, choosing between a direct call and an event,
  adding a cross-cutting concern (auth, metrics, caching, auditing), enforcing
  org/tenant scoping, setting up config/env validation, a job queue worker, or
  graceful shutdown, or refactoring a tangled backend where modules import each
  other's internals —
  even when they don't say the words "architecture" or "plugin". If the task
  smells like "how should I lay this Node backend out" or "these modules are too
  coupled", reach for this skill.
---

# Node.js Modular Architecture

Build Node.js backends the way a car is built: features are **replaceable parts**
that mount onto a **standard socket**, receive **standard wiring**, and can be
unplugged without breaking the rest of the machine.

The whole skill reduces to one rule:

> **Depend on stable contracts, not unstable internals.**

You never eliminate coupling — you *choose where it lives*. Couple to interfaces
(sockets), a shared container (wiring harness), and named events (signal wires).
Never couple to another module's internal files.

## Fixed conventions for this project

These are the house rules. Apply them unless the user explicitly overrides.

**Stack** (Node.js ≥ 20):

- **JavaScript, ESM only.** Never convert the repo to TypeScript. No JSDoc
  annotation comments (`@param`/`@typedef`/`@returns`) — express a "socket" shape
  through the factory signature and a one-line plain comment when it helps; rely
  on Zod schemas and clear code, not doc blocks.
- **Express** for HTTP, **Knex + PostgreSQL** for persistence, **Zod** for
  validation and config, **Winston** for logging, **server-side sessions** for
  auth. A **separate worker process** drains a lease-based PostgreSQL job queue.
  Tests use **Vitest**. → `references/tooling.md`
- **A custom DI container and a custom in-memory event bus** are the default for
  simple/medium apps — both bundled, tested, and ready to copy from
  `assets/di/container.js` and `assets/pubsub/create-event-bus.js`. Graduate to
  Awilix / a real broker only when a concrete pain appears.
- **Don't add a framework or a dependency unless it's necessary**, and prefer
  extending existing helpers/services/repositories over creating new ones.

**Naming:**

- **Files & directories:** kebab-case — `user-profile.repository.js`,
  `telegram-notifier.js`, `create-event-bus.js`. Module files follow
  `<name>.<role>.js` (`order.service.js`, `auth.controller.js`).
- **Variables & functions:** camelCase. **Constants:** UPPER_CASE_SNAKE_CASE.
  **DTO properties:** camelCase. **Database fields & tables:** snake_case, tables
  plural (`orders`, `organizations`).

**Configuration:** read the environment once at startup, validate it with Zod,
fail fast if something required is missing. Keep it in one `env` module the rest
of the app imports — never scatter `process.env.*` reads. Use `.env` files
(dotenv); never commit secrets. → `references/configuration.md`

**Security is backend-enforced and multi-tenant** — this is not optional. Derive
`user_id`, `org_id`, and `role` from the authenticated session; never trust them
from the request body, query, or params. Every repository query for org-owned
entities is scoped by `org_id`; every service that reads or mutates org data
verifies access. → `references/security-tenancy.md`

See the **Hard rules** section near the end before writing code.

## The mental model (the BMW taillight)

| Physical car               | This architecture                          |
| -------------------------- | ------------------------------------------ |
| Standard socket shape      | **Interface / contract** (the "port")      |
| Wiring harness             | **Dependency injection** via a container   |
| Replaceable taillight unit | **Plugin** — a self-registering feature    |
| Signal wires               | **Domain events** on an event bus          |
| Voltage / plug converters  | **Adapters** (repositories, API clients)   |
| Car ignoring LED internals | **Encapsulation** behind a module `index.js` |

Keep these five sentences in your head — they resolve most design questions:

- **Interfaces are the sockets** — the shape a dependency must fit.
- **Dependency injection is the wiring harness** — deps are handed in, never reached for.
- **Plugins are the replaceable parts** — a feature registers itself.
- **Events are the signal wires** — "something happened", broadcast without knowing who listens.
- **Adapters are the converters** — between your app and the outside world (DB, HTTP, Telegram).

## The default architecture

Unless the user asks for something else, reach for:

> **Feature modules + plugin registration + dependency injection + domain events.**

In one sentence: *each feature is a plugin that registers its own routes,
services, repositories, and event subscribers; modules talk through explicit
service interfaces for **required** behavior and through domain events for
**optional** reactions.*

```txt
src/
  app/
    server.js          # builds the app, runs every plugin's register()
    container.js       # the wiring harness — constructs shared infra + config
  worker/
    index.js           # separate process draining the lease-based PG job queue
  infra/               # cross-cutting technical concerns (not business logic)
    config/env.js      # dotenv + Zod, validated once, imported everywhere
    logger/            # Winston + AsyncLocalStorage trace propagation
    events/            # the event bus
    db/                # Knex connection
    lifecycle.js       # graceful shutdown + dev port cleanup
    id.js              # generateShortUID() for string IDs
    auth/              # session → { userId, orgId, role }
  modules/             # one folder per FEATURE (not per technical layer)
    orders/
      index.js              # the PUBLIC SOCKET — the plugin + allowed exports
      order.routes.js       # HTTP adapter (no business logic here)
      order.controller.js   # request/response glue (optional)
      order.service.js      # business logic; verifies access, depends on ports
      order.repository.js   # persistence adapter (Knex; every query org-scoped)
      order.events.js       # event name constants + payload shape (plain comment)
      order.subscribers.js  # this module's reactions to OTHER modules' events
    customers/
    notifications/
    audit/
```

The load-bearing ideas, each with a reference file for full code:

1. **Feature-first folders**, not `controllers/ services/ repositories/`. A
   feature spread across ten technical folders is a taillight with its bulb,
   lens, and screws scattered across the whole car. Keep a feature in one folder
   so you can open it and understand it. → see `references/module-anatomy.md`
2. **Every module exposes a single `index.js` socket.** Others import from
   `modules/orders/index.js` only — never from an internal file. → `references/module-anatomy.md`
3. **Factory functions take dependencies as an argument.** Write
   `createOrderService({ orderRepository, eventBus, logger })`, not a module that
   `import`s the DB and a Telegram client at the top. → `references/wiring.md`
4. **One container wires everything; plugins mount themselves.** → `references/wiring.md`
5. **Domain events decouple optional reactions.** Orders publishes
   `order.created` and does not know that notifications, analytics, and audit all
   react. → `references/events.md`
6. **Cross-cutting concerns are infrastructure, not sprinkled calls.** Logging,
   tracing, auth, metrics belong in middleware or event subscribers — not hand-copied
   into every function. → `references/cross-cutting.md`

## The two decision rules that matter most

Most "where should this go?" questions collapse to these.

### Rule 1 — Direct call vs. event

> **Direct calls are for required behavior. Events are for optional reactions.**

Ask: *if this step fails, must the operation fail?*

- **Yes → direct call.** Saving the order is required, so
  `await orderRepository.create(input)` is a direct, awaited call. If the
  customer's lifetime-value update MUST be consistent with the order, that too is
  a direct call.
- **No → publish an event.** A Telegram alert, an analytics hit, an audit row —
  none should be able to fail order creation. Publish `order.created` and let
  subscribers handle them.

This single rule is what produces the plug-and-play feeling: *want Slack? add a
subscriber. want no notifications? remove the notifications plugin.* The order
module never changes.

### Rule 2 — Where does this concern live?

| Concern                | Home                                        |
| ---------------------- | ------------------------------------------- |
| HTTP request logging   | Express middleware                          |
| Error logging          | Global error handler                        |
| Tracing                | Middleware / OpenTelemetry instrumentation  |
| Metrics                | Middleware + event subscribers              |
| Auth (session → identity) | Middleware                               |
| Input validation       | Route boundary (Zod)                        |
| Notifications          | Event subscribers                           |
| Auditing               | Event subscribers                           |
| Business rules + access checks | Domain service                      |
| DB access (org-scoped) | Repository (a Knex adapter)                 |
| External APIs          | Adapter (e.g. `telegram-notifier.js`)       |
| Config                 | One Zod-validated `env` module              |

Full middleware and subscriber code is in `references/cross-cutting.md`.

## Critical distinction: logging ≠ notifications

Do not use logs as a business workflow engine.

```txt
Logging      = technical observability (what happened, for engineers)
Notification = a business action (tell the customer / admin something)
```

`logger.info('ORDER_CREATED_SEND_TELEGRAM')` is a smell. Publish
`order.created`; let one subscriber log it and a *different* subscriber send
Telegram. Logging has three natural homes — HTTP middleware (technical), service
calls (business milestones), and the global error handler. → `references/cross-cutting.md`

## Workflow: adding a feature (the payoff)

When this architecture is in place, adding `billing` is:

1. Create `modules/billing/` with `index.js`, a service, a repository, routes,
   and any subscribers.
2. In `index.js`, export a plugin whose `register(context)` builds the service
   from injected deps and mounts its routes.
3. Add `billingPlugin` to the plugin list in the container.
4. Decide, per interaction: required → direct call on another module's service
   interface; optional → publish/subscribe an event.

That's the software equivalent of *mount → plug socket → screw in → done.*
Removing the feature is deleting the folder and one line from the plugin list.

## Anti-patterns to refuse (and how to fix)

When refactoring, hunt for these. They're the "bulb wired straight to the
battery" of software.

- **Deep imports across modules** — `import { x } from '../orders/internalValidation.js'`.
  → Import from `modules/orders/index.js`; if it isn't exported there, it's private on purpose.
- **A service importing concrete infra at the top** — `import { db }`, `import { sendTelegram }`.
  → Take them as injected dependencies via a factory function.
- **A business service that knows every downstream** — order service calling
  customers + notifications + analytics directly. → Publish one event; let them subscribe.
- **Cross-cutting calls copy-pasted into every function** — `logger`, `startTrace`,
  `checkPermission`, `recordMetric` inline everywhere. → Move to middleware / subscribers.
- **Folders organized by technical type** for a growing app. → Reorganize by feature.

## Keep the magic honest

Plugins + events are powerful and can turn debugging into "an order was created,
then 17 hidden subscribers ran, one failed — which one?" Prevent this:

- Keep the **plugin list explicit and ordered** in one file — no filesystem auto-discovery magic.
- **Name every subscriber** (`notifications.telegram.onOrderCreated`) so failures are traceable.
- **Log registration and dispatch** — "registered subscriber X for order.created", "publishing order.created → 3 handlers".
- Don't abstract prematurely. Start with a custom in-memory event bus and plain
  factory functions; reach for Awilix, BullMQ, or a real broker only when the pain is real.

The sweet spot is *modular and replaceable, but not over-engineered.*

## Hard rules

Refuse to violate these even when a shortcut is tempting; they encode security,
tenancy, and maintainability the architecture depends on.

- **JavaScript ESM only** — never convert to TypeScript. No new framework, and no
  new dependency, unless it's genuinely necessary. Prefer extending an existing
  helper/service/repository over creating a duplicate.
- **No business logic in Express routes.** Routes validate input and delegate to
  a service. Server authorization lives in service/middleware, never only in the
  frontend.
- **Never trust client-provided identity.** Derive `user_id`, `org_id`, `role`
  from the session — not from body, query, or route params. Don't hardcode
  `user_id`, `org_id`, roles, statuses, or provider-specific behavior.
- **Every org-owned query is scoped by `org_id`;** every service touching org data
  verifies access. Cross-org reads/writes must be impossible. → `references/security-tenancy.md`
- **Don't silently swallow errors.** Use the existing error/logging patterns. (The
  event bus logs and isolates a failing subscriber *by name* — that's deliberate
  and *not* silent; required behavior stays a direct call so it can fail loudly.)
- **Migrations:** don't modify already-applied migrations. **Logs:** never include
  secrets, tokens, raw session cookies, or full credentials.
- **Tests:** never call paid external providers; only claim a command passed if you
  actually ran it. Add/update tests for meaningful behavior changes, and
  specifically cover org scoping, authorization, and worker retry/idempotency.
  → `references/testing.md`

## Security & multi-tenancy (the short version)

Security is backend-enforced; frontend guards are UX only.

- Identity (`user_id`, `org_id`, `role`) comes from the authenticated session.
- Every repository query for org-owned entities is scoped by `org_id`; soft
  deletes are filtered (`is_deleted = false`).
- Every service that reads or mutates org data verifies access; admin-only
  actions are checked in backend service logic or middleware; member reads stay
  org-scoped.
- Owner-protection rules and file upload/download URL scoping are enforced
  server-side. Full patterns and the threat checklist: → `references/security-tenancy.md`

## Process lifecycle

Long-lived processes (the API server and the worker) must terminate cleanly —
stop accepting work, drain in-flight work, close the Knex pool — on `SIGINT`,
`SIGTERM`, **and `SIGHUP`**, with a `forceExitMs` safety net. In development a
watchdog also frees the port when the process is orphaned or the dev session
leader dies (prevents `EADDRINUSE` on restart). Copy `assets/lifecycle.js`.
→ `references/graceful-shutdown.md`

## Reference files

Read the one that matches the task; each has complete, copy-adaptable code.

- `references/module-anatomy.md` — feature-folder layout, the `index.js` socket, file roles, ports as plain signatures, a full org-scoped order module.
- `references/wiring.md` — factory functions, the container, the plugin contract, `server.js` bootstrap, config via the `env` module, DI without a framework.
- `references/events.md` — the in-memory event bus, publishing, named subscribers, the direct-vs-event decision, migrating to a real broker.
- `references/cross-cutting.md` — Winston logging, tracing, metrics, session-based auth, org-scope middleware, validation placement.
- `references/configuration.md` — `.env` + Zod, the single `env` module, fail-fast at startup, never commit secrets.
- `references/security-tenancy.md` — session-derived identity, org scoping every query, authorization in services, log redaction, the tenancy threat checklist.
- `references/database.md` — Knex conventions: snake_case fields, plural tables, `generateShortUID()` string IDs, explicit columns, soft deletes, `trx` in the service layer.
- `references/worker-and-jobs.md` — the separate worker process, the lease-based PostgreSQL job queue, idempotent/retry-safe handlers, bounded concurrency, outbound timeouts.
- `references/logging.md` — the five log categories, the should-I-log framework, AsyncLocalStorage trace propagation, structured-data and redaction rules.
- `references/graceful-shutdown.md` — signal handling, clean pool shutdown, the dev-only port-cleanup watchdog.
- `references/testing.md` — Vitest, what to test (org scoping, authz, retry/idempotency), no paid providers, honest pass claims.
- `references/tooling.md` — the default stack and the signals that justify graduating to Awilix, BullMQ, or a real broker.
- `assets/di/container.js` — copy-ready custom DI container (lazy singletons, cycle detection, child scopes).
- `assets/pubsub/create-event-bus.js` — copy-ready in-memory event bus (named subscribers, per-handler error isolation, broker-shaped interface).
- `assets/lifecycle.js` + `assets/lifecycle.test.js` — drop-in graceful shutdown + its Vitest suite.
- `assets/starter-template/` — the smallest **runnable** Express skeleton (config, Winston, org scoping, graceful shutdown, a Vitest test) to copy for a new project.

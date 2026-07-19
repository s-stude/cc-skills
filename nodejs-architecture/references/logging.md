# Logging Guidelines

> Topic guide for the **nodejs-architecture** skill. Read this when adding,
> reviewing, or auditing log statements — deciding *whether* to log somewhere,
> *which level/category* to use, what structured data to include, and how to
> propagate trace IDs.

A decision-making framework for writing, reviewing, and auditing log messages in
any codebase. In this project the logger is **Winston** (see
`references/cross-cutting.md` for the `create-logger.js` factory that exposes the
`info/warn/error(message, meta)` socket every module depends on).

## Core Principle

Every log message must answer: **"What happened and what should I do about it?"**

Logs exist for operators — the people running the system at 3 AM, debugging a
customer issue, or tracing why a request failed. They do not exist for the code
author to confirm their code ran.

---

## The Five Log Categories

### 1. Error

Something broke. Immediate action is required.

- **When:** An operation failed and cannot recover without intervention
- **Level:** `error`
- **Required data:** error message, error code/type, affected resource identifier, operation that failed
- **Format:** `[error] What failed — Action: what the operator should do`

```
[error] Database connection lost after 3 retries — Action: check database health and network connectivity
[error] Payment processing failed for order_id=abc123 — Action: verify payment gateway status, retry or escalate
```

### 2. Warning

Something is degraded or unexpected but the system continues operating. Needs monitoring — may escalate to an error.

- **When:** A fallback was used, a threshold was approached, something unexpected happened but was handled
- **Level:** `warn`
- **Required data:** what is degraded, current value vs expected, affected scope
- **Format:** `[warning] What's degraded — Monitor: what to watch for escalation`

```
[warning] Memory usage at 85% (threshold: 90%) — Monitor: if it reaches 90%, process will restart
[warning] API response took 4.2s (expected <2s) — Monitor: sustained slowness indicates upstream degradation
```

### 3. Decision

The system chose a path among alternatives. Explains behavior to someone reading logs later who asks "why did it do X instead of Y?"

- **When:** A conditional branch, fallback selection, configuration-driven behavior, or algorithm chose one option over another
- **Level:** `info`
- **Required data:** what was chosen, what alternatives existed, why this choice was made
- **Format:** `[decision] Chose X over Y — reason`

```
[decision] Using cached result (age: 45s) instead of fetching — cache TTL is 60s
[decision] Routing to region us-east-1 — user geo: US, latency: 12ms vs 89ms for eu-west-1
[decision] Skipping notification — user has do-not-disturb enabled until 09:00
```

### 4. Boundary

A request or data crosses between subsystems, services, or external APIs. Enables tracing a request across components.

- **When:** An HTTP call is made/received, a message is published/consumed, a file is read from/written to external storage, a subprocess is spawned
- **Level:** `info`
- **Required data:** source, destination, request/correlation ID, payload summary (not payload itself)
- **Format:** `[boundary] Direction: from → to — summary`

```
[boundary] Outbound: order-service → payment-gateway — charging $49.99 for order_id=abc123
[boundary] Inbound: webhook from stripe — event=payment_intent.succeeded, id=evt_123
[boundary] Publish: render-complete → job-queue — jobId=j42, duration=12.4s
```

### 5. Step

A progress milestone within a multi-step process. Shows how far along the operation got, which is critical for debugging partial failures.

- **When:** A meaningful stage of a larger operation completes (not every function call — only stages an operator would care about)
- **Level:** `info` or `debug` depending on granularity
- **Required data:** step name/number, relevant metrics (count, duration, size), process identifier
- **Format:** `[step] What completed — metrics`

```
[step] Asset download complete — 12 files, 48MB, 3.2s
[step] Database migration applied — version 47→48, 1,204 rows affected
[step] Validation passed — 36 rules checked, 0 violations
```

---

## Log Message Format Convention

```
[category] What happened — context/action guidance
```

- **Category tag** makes logs filterable and scannable
- **What happened** is a concise statement in past tense
- **After the dash** provides the actionable part: what to do (errors), what to watch (warnings), why it happened (decisions), where it went (boundaries), or metrics (steps)

---

## Decision Framework: Should I Log Here?

Use this checklist when deciding whether to add a log statement:

```
1. Would an operator need to know this happened?
   NO  → Don't log
   YES → Continue

2. Is this information already available from another log?
   YES → Don't log (avoid duplicates)
   NO  → Continue

3. Which category does it fit?
   - Did something break?                    → Error
   - Is something degraded but working?      → Warning
   - Did the system choose between options?  → Decision
   - Did data cross a system boundary?       → Boundary
   - Did a stage of a process complete?      → Step
   - None of these?                          → Probably don't log

4. Can I write the message in the format:
   [category] What happened — actionable context?
   NO  → Rethink what you're actually trying to communicate
   YES → Log it
```

---

## What NOT to Log

### "I got here" breadcrumbs

```
// BAD
log.info('Entering processOrder')
log.info('About to validate')
log.info('Validation done')
log.info('Exiting processOrder')
```

These are debugger substitutes, not operational logs. Use a debugger or tracing instead.

### Success confirmations for trivial operations

```
// BAD
log.info('Successfully read config file')
log.info('Database query returned results')
```

If the operation is expected to succeed and failure would be caught elsewhere, don't log the happy path.

### Duplicate signals

If you log at the boundary when a request arrives and again inside the handler that it was received, pick one. If both a caller and callee log the same event, pick one.

### Per-iteration noise in loops

```
// BAD — logs once per item in a potentially large collection
for (const item of items) {
  log.info(`Processing item ${item.id}`)
  process(item)
}

// GOOD — log the step summary
log.info(`[step] Processed ${items.length} items — 2 skipped, 0 errors`)
```

### Scheduled/polling noise

If a cron job or polling loop runs every N seconds, don't log every invocation. Log only when something interesting happens (state change, threshold, error). The queue worker's claim loop is exactly this — don't log every empty poll. → `references/worker-and-jobs.md`

---

## Log Levels Mapping

| Category   | Default Level | Rationale |
|------------|--------------|-----------|
| Error      | `error`      | Requires immediate attention |
| Warning    | `warn`       | Needs monitoring, may escalate |
| Decision   | `info`       | Explains system behavior |
| Boundary   | `info`       | Enables request tracing |
| Step       | `info`       | Shows progress of operations |
| Step (fine) | `debug`     | Granular progress, off by default |

A simple rule: if you'd want to see it in production logs by default, use `info`. If it's only useful when actively debugging, use `debug`.

---

## Async Context Propagation with AsyncLocalStorage

Use `node:async_hooks` `AsyncLocalStorage` to automatically attach trace IDs, request IDs, and user IDs to every log line without passing them through function arguments. This is how a request's `traceId`/`orgId`/`userId` reach a deep service or an event subscriber without threading them through every signature — the same decoupling the architecture prizes elsewhere.

### Setup Pattern

Create a context module that wraps AsyncLocalStorage:

```js
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';

export const asyncContext = new AsyncLocalStorage();

export function runWithTraceId(fn, traceId) {
  const id = traceId || randomUUID().slice(0, 8);
  return asyncContext.run({ traceId: id }, fn);
}

export function getTraceId() {
  return asyncContext.getStore()?.traceId || 'no-trace';
}
```

### Logger Integration

Inject context values into every log line via a format/middleware layer:

```js
// Winston example
const injectTrace = winston.format((info) => {
  const store = asyncContext.getStore();
  if (store?.traceId) info.traceId = store.traceId;
  if (store?.userId) info.userId = store.userId;
  if (store?.requestId) info.requestId = store.requestId;
  return info;
});
```

### Entry Points

Wrap each entry point (script, HTTP handler, queue consumer, cron job) in `asyncContext.run()` so all downstream code inherits the context:

```js
// Script entry point
async function main() {
  await runWithTraceId(async () => {
    await doWork();
  });
}

// Express middleware
app.use((req, res, next) => {
  const store = {
    traceId: req.headers['x-trace-id'] || randomUUID().slice(0, 8),
    requestId: req.headers['x-request-id'] || randomUUID(),
    userId: req.user?.id,
  };
  asyncContext.run(store, next);
});

// Queue consumer
consumer.on('message', (msg) => {
  asyncContext.run({ traceId: msg.traceId || randomUUID().slice(0, 8) }, () => {
    processMessage(msg);
  });
});
```

### Rules

1. **One `run()` per entry point** — never nest `run()` calls unless deliberately overriding context (e.g., spawning a sub-workflow with its own trace)
2. **Never pass traceId as a function parameter** — that defeats the purpose; let AsyncLocalStorage propagate it implicitly
3. **Always provide a fallback** — `getTraceId()` must return a safe default (`'no-trace'`) for code paths that run outside a context (module-level initialization, tests)
4. **Keep the store minimal** — only put identifiers needed for log correlation (traceId, requestId, userId). Don't store request bodies or mutable state
5. **Propagate across service boundaries** — when making outbound HTTP/gRPC calls, read the traceId from the store and pass it as a header (`x-trace-id`) so downstream services can continue the trace

### What Goes in the Store

| Field | Source | Purpose |
|-------|--------|---------|
| `traceId` | Generated at entry point or received from upstream header | Correlates all logs from one workflow execution |
| `requestId` | Per-HTTP-request unique ID | Distinguishes concurrent requests within the same trace |
| `userId` | Auth middleware / token payload | Ties logs to a specific user for debugging customer issues |

Store identifiers only — `userId`, `orgId`, `traceId`. This dovetails with the tenancy rule in `references/security-tenancy.md`: log *who and which org* as IDs, never the session cookie, token, or credentials behind them.

### Anti-patterns

```js
// BAD — manually threading traceId through every function
async function processOrder(order, traceId) {
  logger.info({ traceId }, 'processing');
  await chargePayment(order, traceId);
  await sendEmail(order, traceId);
}

// GOOD — AsyncLocalStorage propagates automatically
async function processOrder(order) {
  logger.info('processing'); // traceId injected by logger format
  await chargePayment(order);
  await sendEmail(order);
}
```

---

## Structured Data Guidelines

### Always include

- **Identifiers:** job ID, request ID, user ID, order ID — whatever connects the log to a traceable entity
- **Timing:** duration of operations (in seconds or milliseconds, be consistent)
- **Counts:** how many items processed, how many succeeded/failed
- **Context:** operation name, component name

### Never include

- **Secrets:** API keys, tokens, passwords, connection strings
- **PII:** email addresses, phone numbers, physical addresses, full names (use IDs instead)
- **Large payloads:** full request/response bodies, file contents, database row dumps
- **Redundant data:** information already in the log context (timestamp, hostname — these are added by the logging framework)

### Prefer structured fields over string interpolation

```
// Prefer this
logger.info({ jobId, duration, frameCount }, '[step] Render complete')

// Over this
logger.info(`[step] Render complete for job ${jobId} in ${duration}s (${frameCount} frames)`)
```

Structured fields are searchable, filterable, and aggregatable. String interpolation is human-readable but machine-hostile.

---

## Audit Process

How to audit existing logs in a codebase:

### Step 1: Inventory

Find all log statements and extract them into a list with file location, current level, and message text.

```bash
grep -rn 'log\.\(info\|warn\|error\|debug\)' src/ > log-inventory.txt
```

### Step 2: Categorize

For each log message, assign one of the five categories (error, warning, decision, boundary, step) or mark it as "remove."

### Step 3: Evaluate each message

For each log, ask:

1. **Does it answer "what happened and what should I do?"** — If not, rewrite or remove.
2. **Is the category correct?** — An `info` that describes a failure should be `error`. A `warn` that's actually a normal decision should be `info`.
3. **Does it include the right structured data?** — Check against the required data for its category.
4. **Is it a duplicate?** — Does another log already capture this same event?
5. **Is it noise?** — Would this fire on every request, every loop iteration, or every poll cycle without adding information?

### Step 4: Rewrite

Apply the message format convention: `[category] What happened — context/action guidance`

Add missing structured data fields. Remove redundant information.

### Step 5: Verify deduplication

After rewriting, check that no two log messages in the same code path capture the same event. Also check across caller/callee boundaries.

### Step 6: Review log volume

Estimate how many log lines per request/operation the rewritten logs will produce. If the answer is more than 5-10 per typical operation, look for opportunities to consolidate step logs or move verbose entries to `debug` level.

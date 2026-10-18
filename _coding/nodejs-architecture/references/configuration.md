# Configuration — one validated `env`, read once

> Topic guide for the **nodejs-architecture** skill. Read this when you're wiring
> config/env into a service, deciding where `process.env` reads may live, adding a
> new setting, or setting up `.env` files — anything about how the app learns its
> runtime configuration.

Configuration is a **cross-cutting concern with exactly one home** — the same
"where does this concern live?" logic as *Rule 2* in `SKILL.md`. Config lives in a
single `env` module; the rest of the app imports `env`, never `process.env`.

## Validate once, at startup, and fail fast

Read the environment once when the process boots, validate the whole shape with
Zod, and **exit immediately if anything required is missing or malformed**. A
process that boots half-configured is worse than one that refuses to boot: it
starts serving traffic and then explodes on the first request that needs the
missing value — in production, at 3am, far from the real cause. Failing fast turns
"a required secret is unset" into a loud crash on line one of startup, with a
message naming the offending variable.

```js
// src/infra/config/env.js
import dotenv from 'dotenv';
import { z } from 'zod';
import { logger } from '../logger/logger.js';

dotenv.config();

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.string().default('3000'),
  DATABASE_URL: z.string(),
  SECRET_KEY: z.string().min(32),
});

const parseEnv = () => {
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    logger.error('Environment validation failed', { errors: result.error.errors });
    process.exit(1);
  }
  return result.data;
};

export const env = parseEnv();
```

Notes on the pattern:

- `safeParse` + `process.exit(1)` is deliberate — we don't throw and hope a caller
  catches it; a misconfigured process should die at import time.
- Log the **validation errors**, never the values. Zod's `error.errors` name which
  keys failed without printing secrets. Don't log `result.data`.
- Environment variables arrive as strings. Keep `PORT` a string here (or coerce
  with `z.coerce.number()`), but do the coercion **in the schema** so every reader
  gets the parsed type — not scattered `Number(process.env.PORT)` at call sites.

## One `env` module, imported everywhere — never scattered `process.env`

`env` is to configuration what the container is to dependencies: **one wiring
place**. Scattered `process.env.DATABASE_URL` reads are the config equivalent of a
service reaching for concrete infra at the top of a file — you lose validation,
you lose a single source of truth, and a typo (`process.env.DATABSE_URL`) silently
becomes `undefined` instead of a startup crash.

```js
// BAD — scattered, unvalidated, un-typed, un-greppable
const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// GOOD — one validated home
import { env } from '../infra/config/env.js';
const pool = new Pool({ connectionString: env.DATABASE_URL });
```

Rule of thumb: `process.env.*` appears in **exactly one file** — `env.js`.
Everything else imports `env`.

## How config plugs into the container

The container is the only place that reads `env` to build infrastructure; it then
passes plain **values** into factories, not the whole `env` object. A repository
factory should ask for `{ db }`, not for `env` — it doesn't need to know
configuration exists. This keeps modules testable: a test constructs a service
with a fake db, never touching the environment. → `references/wiring.md`

```js
// src/app/container.js
import { env } from '../infra/config/env.js';
import { createDbConnection } from '../infra/db/connection.js';

export function buildContainer() {
  const db = createDbConnection({ connectionString: env.DATABASE_URL });
  // factories receive resolved values/deps, not `env` itself
  // ...
  return { db, env };
}
```

The **worker** process imports the same `env` module — one schema governs both the
API server and the queue worker, so they can't disagree about configuration or
drift apart. → `references/worker-and-jobs.md`

## Adding a new setting = add a field to the schema

There's one move: add a key to `envSchema`. Because validation runs at startup,
forgetting to set it in production is caught the instant that process boots — the
fail-fast net does the enforcement for you. No new setting is "optional to wire";
if it's in the schema, prod must provide it (or you give it a `.default(...)`).

```js
const envSchema = z.object({
  // ...existing keys
  REDIS_URL: z.string().url(),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});
```

## `.env`, `.env.example`, and never committing secrets

- **`.env`** holds real local values and is **git-ignored** — always. It contains
  secrets; it never enters version control.
- **`.env.example`** is committed. It lists every key the schema expects with
  **placeholder or empty values** — it's living documentation of the config
  surface and the first thing a new developer copies to `.env`.
- `.gitignore` must contain `.env` (and `.env.*.local`). Keep `.env.example`
  tracked.

```txt
# .env.example  (committed — no real values)
NODE_ENV=development
PORT=3000
DATABASE_URL=postgres://user:pass@localhost:5432/app
SECRET_KEY=change-me-to-a-32+-char-random-string
```

```txt
# .gitignore
.env
.env.*.local
```

Never commit secrets, and never let them reach logs — no tokens, keys, connection
strings with passwords, or session cookies in log output. The `env.js` error path
above logs only which keys failed validation, not their contents. Broader redaction
rules and the secrets-handling checklist live in
`references/security-tenancy.md`. For where dotenv and the tooling sit in the
default stack, see `references/tooling.md`.

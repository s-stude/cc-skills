# Security and multi-tenancy — trust the session, nothing else

> Topic guide for the **nodejs-architecture** skill. Read this when you touch
> authentication, authorization, org/tenant scoping, file upload/download URLs,
> or anything where one organization must never see another's data. This is the
> most safety-critical reference — when in doubt, prefer the stricter rule.

Security is **backend-enforced**. Frontend guards (hiding a button, disabling a
menu) are for UX only — they make the app pleasant, never safe. Assume every
request is hostile and hand-crafted: an attacker can send any body, any query
string, any route param. The only thing they cannot forge is a valid
server-side session. So identity comes from the session and nowhere else.

The whole reference reduces to one rule:

> **Derive `user_id`, `org_id`, and `role` from the session; scope every
> org-owned query by `org_id`; verify access in the service.**

Follow the request lifecycle below and enforce at every layer — defense in depth
means a mistake at one layer is caught by the next.

## 1. Identity comes from the session, never the request

A session cookie is the only trustworthy input. Middleware turns it into
`req.auth = { userId, orgId, role }`, and the rest of the app reads identity from
there. Never read `userId`, `orgId`, or `role` from `req.body`, `req.query`, or
`req.params` — those are attacker-controlled.

```js
// src/infra/auth/require-auth.js
export function createRequireAuth({ sessionStore, logger }) {
  return async function requireAuth(req, res, next) {
    try {
      const sessionId = req.cookies?.sid;
      if (!sessionId) {
        return res.status(401).json({ error: 'authentication_required' });
      }

      const session = await sessionStore.get(sessionId);
      if (!session) {
        return res.status(401).json({ error: 'authentication_required' });
      }

      // Identity is derived ONLY from the server-side session record.
      req.auth = {
        userId: session.user_id,
        orgId: session.org_id,
        role: session.role,
      };

      return next();
    } catch (error) {
      return next(error);
    }
  };
}
```

Mount it before any route that touches org data. From here on, `req.auth` is the
single source of truth for who is asking — treat everything else in the request
as untrusted input to be validated, not identity to be trusted.

## 2. Routes pass ONLY `req.auth` plus validated input to the service

The route's job is to validate the *payload* and forward the *actor*. It must
never let the client smuggle identity in through the body. Spreading `req.body`
into the actor is the classic tenancy hole.

```js
// modules/pages/page.routes.js
import express from 'express';

export function createPageRoutes({ pageService }) {
  const router = express.Router();

  router.post('/', async (req, res, next) => {
    try {
      // ANTI-PATTERN — client controls its own org/role. Never do this:
      //   const actor = { ...req.body };
      //   await pageService.createPage(actor, req.body);
      // Attacker sends { "orgId": "victim-org" } and writes into another tenant.

      // CORRECT — actor from the session, input validated separately.
      const input = parsePageInput(req.body); // Zod; contains NO identity fields
      const page = await pageService.createPage(req.auth, input);
      res.status(201).json(page);
    } catch (error) {
      next(error);
    }
  });

  return router;
}
```

Validated input carries *data* (a title, a URL). It never carries `orgId`,
`userId`, or `role` — strip those from any schema. Business logic and
authorization live in the service, never in the route. → `references/module-anatomy.md`

## 3. Services verify access — every method takes an `actor`

Every service method that reads or mutates org data takes an `actor`
(`{ userId, orgId, role }`) as its first argument and enforces two things: the
data belongs to the actor's org, and the actor's role is allowed to do this.
Keep the checks in tiny shared helpers so they read the same everywhere.

```js
// src/infra/auth/access.js
export function requireRole(actor, allowedRoles) {
  if (!allowedRoles.includes(actor.role)) {
    const error = new Error('forbidden');
    error.status = 403;
    throw error;
  }
}

export function assertSameOrg(actor, entity) {
  // Missing entity and wrong-org entity are treated identically on purpose —
  // see section 5 (don't leak existence).
  if (!entity || entity.org_id !== actor.orgId) {
    const error = new Error('not_found');
    error.status = 404;
    throw error;
  }
}
```

An admin-only mutation checks the role in the service, not the frontend. A
member-only read still passes `orgId` down to the repository — read access is not
a license to skip scoping.

```js
// modules/sources/source.service.js
import { requireRole, assertSameOrg } from '../../infra/auth/access.js';

export function createSourceService({ sourceRepository, logger }) {
  return {
    // Admin-only: delete a source. Role is enforced server-side.
    async deleteSource(actor, sourceId) {
      requireRole(actor, ['owner', 'admin']);

      const source = await sourceRepository.findById(actor.orgId, sourceId);
      assertSameOrg(actor, source);

      await sourceRepository.softDelete(actor.orgId, sourceId);
      logger.info('Source deleted', {
        user_id: actor.userId,
        org_id: actor.orgId,
        source_id: sourceId,
      });
    },

    // Member read: any member may list, but ALWAYS org-scoped.
    async listSources(actor) {
      return sourceRepository.listByOrg(actor.orgId);
    },
  };
}
```

## 4. Repositories are scoped by `org_id` — defense in depth

The service is the first gate; the repository is the backstop. Even if a service
method forgot to check, the repository makes `org_id` a **required parameter** so
a query can never accidentally span tenants. Never expose a `findById(id)` that
ignores the org — take `orgId` first and put it in the `WHERE` clause.

```js
// modules/sources/source.repository.js
export function createSourceRepository({ db }) {
  return {
    async findById(orgId, sourceId) {
      return (
        (await db('sources')
          .where({ id: sourceId, org_id: orgId, is_deleted: false })
          .first()) ?? null
      );
    },

    async listByOrg(orgId) {
      return db('sources')
        .where({ org_id: orgId, is_deleted: false })
        .orderBy('created_at', 'desc');
    },

    async softDelete(orgId, sourceId) {
      // org_id in the WHERE clause guarantees a cross-org delete affects 0 rows.
      return db('sources')
        .where({ id: sourceId, org_id: orgId })
        .update({ is_deleted: true });
    },
  };
}
```

Every org-owned table (pages, sources, documents, prompts, jobs, members, search
results) follows this: `org_id` is a required argument and always in the `WHERE`
clause, alongside the soft-delete filter. → `references/database.md`

## 5. Owner protection and cross-org isolation

A user must not reach another org's pages, sources, documents, prompts, jobs,
members, or search results. When the entity belongs to a different org, return
**404, not 403** — a 403 confirms the record exists, leaking existence and an ID
an attacker can probe. `assertSameOrg` above already collapses "missing" and
"wrong org" into the same 404.

```js
// modules/documents/document.service.js
import { assertSameOrg } from '../../infra/auth/access.js';

export function createDocumentService({ documentRepository }) {
  return {
    async getDocument(actor, documentId) {
      const document = await documentRepository.findById(actor.orgId, documentId);
      // Another org's document was never returned by the org-scoped query,
      // so this throws 404 — the caller cannot tell it exists.
      assertSameOrg(actor, document);
      return document;
    },
  };
}
```

Owner-protection rules are enforced the same way, server-side: you cannot remove
the last owner, and you cannot demote or delete an owner unless you are one. Put
those checks in the service, never in the UI.

```js
// modules/members/member.service.js
import { requireRole } from '../../infra/auth/access.js';

export function createMemberService({ memberRepository }) {
  return {
    async removeMember(actor, targetUserId) {
      requireRole(actor, ['owner']);

      const target = await memberRepository.findByUser(actor.orgId, targetUserId);
      assertSameOrg(actor, target); // cross-org target → 404

      if (target.role === 'owner') {
        const owners = await memberRepository.countOwners(actor.orgId);
        if (owners <= 1) {
          const error = new Error('cannot_remove_last_owner');
          error.status = 409;
          throw error;
        }
      }

      await memberRepository.remove(actor.orgId, targetUserId);
    },
  };
}
```

## 6. File upload and download URLs are org-scoped

A signed URL is a capability — if it is not tied to an org, it is a cross-tenant
leak. Key the storage path and the signature by `org_id`, and re-check the actor's
org when the URL is used. Never build a download URL from a client-supplied org.

```js
// modules/documents/document.service.js
export function createDocumentStorageService({ storage, documentRepository }) {
  return {
    async getDownloadUrl(actor, documentId) {
      const document = await documentRepository.findById(actor.orgId, documentId);
      assertSameOrg(actor, document);

      // Path and signature are scoped to the authenticated org.
      return storage.signGetUrl({
        key: `org/${actor.orgId}/documents/${document.storage_key}`,
        expiresInSeconds: 300,
      });
    },

    async getUploadUrl(actor, filename) {
      return storage.signPutUrl({
        key: `org/${actor.orgId}/uploads/${filename}`,
        expiresInSeconds: 300,
      });
    },
  };
}
```

On upload completion and on every download, re-derive the org from `req.auth` and
confirm the stored `org_id` matches — a signed URL is not a substitute for a scope
check.

## 7. Logs must never leak secrets

Logging is observability, not a place to dump credentials. Never log secrets,
access tokens, raw session cookies, or full provider credentials. Log the *stable
identifiers* — `user_id`, `org_id`, `role` — so you can trace a request without
exposing anything sensitive.

```js
// GOOD — identifiers only, no secrets.
logger.info('Prompt executed', {
  user_id: actor.userId,
  org_id: actor.orgId,
  role: actor.role,
  prompt_id: promptId,
});

// BAD — leaks a credential into the log stream forever.
logger.info('Provider call', { apiKey: provider.apiKey, cookie: req.headers.cookie });
```

Redaction belongs in the logger configuration too, so an accidental object spread
can't leak. → `references/logging.md` and `references/cross-cutting.md`

## 8. Cross-org access must be covered by tests

Tenancy holes are silent until exploited, so prove isolation with tests: a member
of org A must get a 404 (not the record, not a 403) when requesting org B's page,
document, prompt, job, member, or search result. Also test that role checks reject
a member attempting an admin-only action, and that owner-protection rules hold.
→ `references/testing.md`

## Never do these

- **Trust identity from the request.** `orgId` / `userId` / `role` from body,
  query, or params is an attacker input, not identity. Only `req.auth` counts.
- **Put authorization only in the frontend.** UI guards are UX; the server must
  re-check every time.
- **Put business or authz logic in Express routes.** Routes validate input and
  forward `req.auth`; services decide.
- **Hardcode** `user_id`, `org_id`, roles, statuses, or provider-specific
  behavior. Derive and configure them.
- **Return 403 for another org's entity.** Return 404 — don't leak existence.
- **Log** secrets, tokens, raw cookies, or full provider credentials.

## Tenancy checklist

Before shipping any endpoint or service that touches org data:

- [ ] Identity comes only from `req.auth` (session), never from body/query/params.
- [ ] `requireAuth` runs before every org-scoped route; no session → 401.
- [ ] Routes pass `req.auth` + validated input; the input schema has no identity fields.
- [ ] Every service method takes an `actor` and calls `requireRole` / `assertSameOrg` as needed.
- [ ] Admin-only actions check the role server-side; member reads are still org-scoped.
- [ ] Every repository method for an org-owned entity requires `org_id` in the `WHERE` clause.
- [ ] Cross-org access returns 404 (not 403, not the record); owner-protection rules enforced server-side.
- [ ] File upload/download URLs are keyed and re-checked by the authenticated `org_id`.
- [ ] Logs contain `user_id` / `org_id` / `role` only — no secrets, tokens, cookies, or credentials.
- [ ] Tests cover cross-org denial, role rejection, and owner protection.
```

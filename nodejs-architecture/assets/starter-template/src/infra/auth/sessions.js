// Server-side session store (in-memory for the starter). In a real app this is
// backed by the DB / a session store and populated at login. The KEY POINT:
// identity lives on the SERVER, keyed by an opaque session token. The client
// only ever sends the token — never its own userId/orgId/role.
// See references/security-tenancy.md.

export function createSessions() {
  // Seeded demo sessions so the starter runs. Token -> identity.
  const store = new Map([
    ['demo-session-org-a', { userId: 'user_a', orgId: 'org_a', role: 'admin' }],
    ['demo-session-org-b', { userId: 'user_b', orgId: 'org_b', role: 'member' }],
  ]);

  return {
    // Resolve identity from the opaque token the client presents.
    async get(req) {
      const token = (req.headers.authorization ?? '').replace('Bearer ', '');
      return store.get(token) ?? null;
    },
  };
}

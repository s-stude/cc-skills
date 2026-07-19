// Turns the server-side session into req.auth = { userId, orgId, role } before
// any route runs. Identity is NEVER read from the body, query, or params.
// See references/security-tenancy.md.

export function createRequireAuth({ sessions, logger }) {
  return async function requireAuth(req, res, next) {
    try {
      const session = await sessions.get(req);
      if (!session) return res.status(401).json({ error: 'Unauthorized' });
      req.auth = { userId: session.userId, orgId: session.orgId, role: session.role };
      next();
    } catch (error) {
      logger.warn('Auth failed', { path: req.path });
      res.status(401).json({ error: 'Unauthorized' });
    }
  };
}

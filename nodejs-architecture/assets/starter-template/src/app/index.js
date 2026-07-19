// Process entry point. Listen, then wire graceful shutdown so the port is freed
// (and, in a real app, the DB pool closed) on any exit. See
// references/graceful-shutdown.md.

import { createServer } from './server.js';
import { env } from '../infra/config/env.js';
import { installGracefulShutdown, sessionPidFromEnv } from '../infra/lifecycle.js';

const { app, db, logger } = await createServer();

const server = app.listen(env.PORT, () => {
  logger.info(`listening on http://localhost:${env.PORT}`);
  logger.info(
    `try: curl -X POST localhost:${env.PORT}/orders ` +
      `-H 'authorization: Bearer demo-session-org-a' ` +
      `-H 'content-type: application/json' -d '{"customerId":"cust_1","total":42}'`,
  );
});

const isDev = env.NODE_ENV !== 'production';
installGracefulShutdown({
  name: 'API server',
  logger,
  watchOrphan: isDev,
  sessionPid: isDev ? sessionPidFromEnv() : undefined,
  onShutdown: async () => {
    await new Promise((resolve) => server.close(resolve)); // stop new connections
    // In a real app: await db.destroy(); // close the Knex pool
    void db;
  },
});

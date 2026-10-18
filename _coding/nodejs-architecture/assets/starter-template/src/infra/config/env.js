// Read the environment ONCE at startup and validate it with Zod. Fail fast if
// something required is missing rather than booting half-configured. The rest of
// the app imports `env` from here — never scatter process.env.* reads.
// See references/configuration.md.

import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().default(3000),
  LOG_LEVEL: z.enum(['error', 'warn', 'info', 'debug']).default('info'),
  TELEGRAM_BOT_TOKEN: z.string().default('fake-token'),
  TELEGRAM_CHAT_ID: z.string().default('fake-chat'),
  // In a real app: DATABASE_URL: z.string(), SECRET_KEY: z.string().min(32), ...
});

const result = envSchema.safeParse(process.env);
if (!result.success) {
  // Can't use the app logger yet — it depends on env. Fail loudly and exit.
  console.error('[error] Environment validation failed —', result.error.flatten().fieldErrors);
  process.exit(1);
}

export const env = result.data;

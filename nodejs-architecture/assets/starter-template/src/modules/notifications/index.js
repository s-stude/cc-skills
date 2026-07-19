// The PUBLIC SOCKET for the notifications feature.
//
// This plugin registers ONLY event subscribers — no routes. Remove it from the
// plugin list in container.js and orders still work; only notifications stop.
// That is the "unplug and forget" behavior.

import { createTelegramNotifier } from './telegram-notifier.js';
import { registerNotificationSubscribers } from './notification.subscribers.js';

export const notificationsPlugin = {
  name: 'notifications',
  register({ eventBus, env, logger }) {
    const telegram = createTelegramNotifier({
      botToken: env.TELEGRAM_BOT_TOKEN,
      chatId: env.TELEGRAM_CHAT_ID,
      logger,
    });

    registerNotificationSubscribers({ eventBus, telegram });
  },
};

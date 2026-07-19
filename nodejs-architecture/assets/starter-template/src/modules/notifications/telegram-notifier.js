// Adapter for an external system (Telegram). Keeps the API-specific details
// here so business code depends only on a small send-a-message shape.
// In the starter it just logs; wire a real Telegram call where indicated.

export function createTelegramNotifier({ botToken, chatId, logger }) {
  return {
    async sendMessage(text) {
      // Real implementation would POST to the Telegram Bot API using botToken/chatId.
      logger.info('Telegram message sent (stub)', { chatId, text });
    },
  };
}

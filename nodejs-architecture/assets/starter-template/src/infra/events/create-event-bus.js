// In-memory pub/sub with named subscribers and per-handler error isolation.
// Same as skills/nodejs-architecture/assets/pubsub/create-event-bus.js — copied
// here so the starter runs standalone. See references/events.md.

export function createEventBus({ logger } = {}) {
  const log = logger ?? { info: () => {}, warn: () => {}, error: console.error };
  const handlers = new Map(); // eventName -> [{ name, handler }]

  return {
    subscribe(eventName, handler, { name } = {}) {
      if (typeof handler !== 'function') {
        throw new TypeError(`Handler for "${eventName}" must be a function`);
      }
      if (!handlers.has(eventName)) handlers.set(eventName, []);
      const subscriberName = name ?? handler.name ?? 'anonymous';
      const entry = { name: subscriberName, handler };
      handlers.get(eventName).push(entry);
      log.info('Registered event subscriber', { eventName, subscriber: subscriberName });
      return function unsubscribe() {
        const list = handlers.get(eventName);
        const idx = list?.indexOf(entry) ?? -1;
        if (idx !== -1) list.splice(idx, 1);
      };
    },

    async publish(eventName, payload) {
      const subs = handlers.get(eventName) ?? [];
      log.info('Publishing event', { eventName, handlerCount: subs.length });
      for (const { name, handler } of subs) {
        try {
          await handler(payload);
        } catch (error) {
          // Isolated, but LOGGED with the subscriber name — not silently swallowed.
          log.error('Event handler failed', { eventName, subscriber: name, error: error.message });
        }
      }
    },

    subscribers(eventName) {
      return (handlers.get(eventName) ?? []).map((s) => s.name);
    },
  };
}

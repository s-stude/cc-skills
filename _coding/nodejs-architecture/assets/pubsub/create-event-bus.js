// A tiny in-memory publish/subscribe event bus for single-process Node.js apps.
// Named subscribers + per-handler error isolation make it debuggable. No deps.
//
// The interface — publish(name, payload) / subscribe(name, handler, opts) — is
// deliberately broker-shaped, so you can later swap in BullMQ / RabbitMQ / Redis
// Streams / NATS behind the SAME shape without touching modules.
//
// Usage:
//   const bus = createEventBus({ logger });
//   bus.subscribe('order.created', async (e) => { ... }, { name: 'notify.onOrderCreated' });
//   await bus.publish('order.created', { orderId: 'ord_1' });
//
// Design choice: handlers run SEQUENTIALLY for predictable log order, and a
// handler that throws is logged and skipped — one bad subscriber must not break
// the others or fail the publish. This is on purpose: events are for OPTIONAL
// reactions. Anything that must succeed should be a direct call, not an event.

export function createEventBus({ logger } = {}) {
  const log = logger ?? {
    info: () => {},
    warn: () => {},
    error: (msg, meta) => console.error(msg, meta),
  };

  const handlers = new Map(); // eventName -> [{ name, handler }]

  return {
    // Returns an unsubscribe function. Pass opts.name to make failures traceable.
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
        if (!list) return;
        const idx = list.indexOf(entry);
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
          log.error('Event handler failed', {
            eventName,
            subscriber: name,
            error: error.message,
          });
        }
      }
    },

    // Names of subscribers registered for an event — handy for boot/debug logs.
    subscribers(eventName) {
      return (handlers.get(eventName) ?? []).map((s) => s.name);
    },
  };
}

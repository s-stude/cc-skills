# Events — the signal wires

Events let modules react to each other **without knowing each other**. Orders
announces "an order was created" and moves on; notifications, analytics, and
audit each decide what that means to them. This is what makes features
plug-and-play: add a subscriber to add behavior, remove a plugin to remove it —
the publisher never changes.

Plain **JavaScript (ESM)**. A ready-to-copy in-memory pub/sub ships at
`assets/pubsub/create-event-bus.js`; the core of it is shown below.

## The decision: direct call vs. event

> **Direct calls are for required behavior. Events are for optional reactions.**

Work it through with order creation:

| Step                         | Required for order to succeed? | Mechanism      |
| ---------------------------- | ------------------------------ | -------------- |
| Save the order               | Yes                            | direct call    |
| Send a Telegram alert        | No                             | event          |
| Track analytics              | No                             | event          |
| Write an audit row           | No                             | event          |
| Update customer stats        | Depends                        | see below      |

For the ambiguous one: if order creation *must* fail when the customer update
fails (strong consistency), make it a **direct call**. If it can happen
eventually and a failure there shouldn't roll back the order, publish an
**event**. Let the business requirement decide — not convenience.

The tell for a design gone wrong:

```js
// BAD — the order service now knows about three other modules.
export async function createOrder(input) {
  const order = await createOrderInDb(input);
  await updateCustomerStats(input.customerId);   // reaching into customers
  await sendTelegramMessage('Order created');    // reaching into notifications
  await trackAnalytics('order_created');         // reaching into analytics
  return order;
}
```

```js
// GOOD — one announcement; downstream modules subscribe.
export function createOrderService({ orderRepository, eventBus, logger }) {
  return {
    async createOrder(actor, input) {
      const order = await orderRepository.create(actor.orgId, input);
      logger.info('Order created', { orderId: order.id, orgId: actor.orgId });
      // Carry orgId so subscribers stay org-scoped. → references/security-tenancy.md
      await eventBus.publish('order.created', {
        orderId: order.id,
        orgId: order.orgId,
        customerId: order.customerId,
        total: order.total,
      });
      return order;
    },
  };
}
```

## The in-memory event bus

Named subscribers and per-handler error isolation are the two features that keep
this debuggable. A handler that throws is logged and skipped — one bad subscriber
must not take down the others or fail the publish.

```js
// infra/events/create-event-bus.js
export function createEventBus({ logger }) {
  const handlers = new Map(); // eventName -> [{ name, handler }]

  return {
    // subscribe(eventName, handler, { name }) — name the subscriber for traceable logs
    subscribe(eventName, handler, { name } = {}) {
      if (!handlers.has(eventName)) handlers.set(eventName, []);
      const subscriberName = name ?? handler.name ?? 'anonymous';
      handlers.get(eventName).push({ name: subscriberName, handler });
      logger.info('Registered event subscriber', { eventName, subscriber: subscriberName });
    },

    async publish(eventName, payload) {
      const subs = handlers.get(eventName) ?? [];
      logger.info('Publishing event', { eventName, handlerCount: subs.length });

      for (const { name, handler } of subs) {
        try {
          await handler(payload);
        } catch (error) {
          // Isolate failures: one subscriber must not break the others.
          logger.error('Event handler failed', {
            eventName,
            subscriber: name,
            error: error.message,
          });
        }
      }
    },
  };
}
```

Notes:

- Handlers run **sequentially** here so log order is predictable. If a slow
  subscriber shouldn't block others, switch the loop to `Promise.allSettled` over
  the handlers — but keep the per-handler try/catch semantics.
- The bus **isolates** a failing subscriber *by design* (optional reactions) —
  but note it **logs** the failure with the subscriber's name; it does not
  *silently* swallow it. That distinction matters: the hard rule "don't silently
  swallow errors" still holds. **Required** behavior must be a direct call,
  precisely because it should be able to fail the operation loudly.
- Events are optional, in-memory, best-effort reactions. When work must be
  **durable and retriable** (survive a crash, run in another process), it's a
  job, not an event — enqueue it on the lease-based PostgreSQL queue instead.
  → `references/worker-and-jobs.md`

## Subscribers live with the reacting module

Each module owns its reactions in a `*.subscribers.js` file and registers them in
its plugin. Names make failures traceable.

```js
// modules/notifications/notification.subscribers.js
import { ORDER_EVENTS } from '../orders/index.js';

export function registerNotificationSubscribers({ eventBus, telegram }) {
  eventBus.subscribe(
    ORDER_EVENTS.CREATED,
    async (event) => {
      await telegram.sendMessage(`New order ${event.orderId}, total: ${event.total}`);
    },
    { name: 'notifications.telegram.onOrderCreated' },
  );
}
```

```js
// modules/customers/customer.subscribers.js
import { ORDER_EVENTS } from '../orders/index.js';

export function registerCustomerSubscribers({ eventBus, customerService }) {
  eventBus.subscribe(
    ORDER_EVENTS.CREATED,
    async (event) => customerService.updateOrderStats(event.customerId),
    { name: 'customers.onOrderCreated.updateStats' },
  );
}
```

Wire them in the module's plugin `register()`:

```js
// modules/notifications/index.js
import { createTelegramNotifier } from './telegram-notifier.js';
import { registerNotificationSubscribers } from './notification.subscribers.js';

export const notificationsPlugin = {
  name: 'notifications',
  register({ eventBus, config, logger }) {
    const telegram = createTelegramNotifier({
      botToken: config.telegram.botToken,
      chatId: config.telegram.chatId,
      logger,
    });
    registerNotificationSubscribers({ eventBus, telegram });
  },
};
```

Remove `notificationsPlugin` from the plugin list and orders still work — only
notifications disappear. That is the "unplug and forget" behavior.

## Keep the magic honest

Event systems become "17 hidden subscribers ran, one failed, where?" if you let
them. Guardrails:

- **Name every subscriber** — the logs above turn a mystery failure into a line
  you can grep.
- **Log registration and dispatch** — you can see, at boot, exactly who listens
  to what.
- **Keep the plugin list explicit** so the full set of subscribers is knowable
  from one file. Never auto-discover subscribers by scanning directories.

## Migrating to a real broker later

The interface — `publish(name, payload)` / `subscribe(name, handler, opts)` — is
deliberately broker-shaped. When in-memory isn't enough (multiple processes,
durability, retries), implement the *same* interface over BullMQ, Redis Streams,
RabbitMQ, NATS, or Kafka and swap it in the container. Modules that only depend on
the interface don't change. Start in-memory; graduate only when the need is real.

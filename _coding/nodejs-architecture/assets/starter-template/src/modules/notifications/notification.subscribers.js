// This module's REACTIONS to other modules' events. Named subscribers so a
// failure shows up in logs as a specific name, not "anonymous handler".

import { ORDER_EVENTS } from '../orders/index.js';

export function registerNotificationSubscribers({ eventBus, telegram }) {
  eventBus.subscribe(
    ORDER_EVENTS.CREATED,
    async (event) => {
      await telegram.sendMessage(`New order ${event.orderId} (org ${event.orgId}), total: ${event.total}`);
    },
    { name: 'notifications.telegram.onOrderCreated' },
  );
}

// The PUBLIC SOCKET for the orders feature. Others import only from here.

import { createOrderRoutes } from './order.routes.js';
import { createOrderService } from './order.service.js';
import { createOrderRepository } from './order.repository.js';
import { ORDER_EVENTS } from './order.events.js';

// Event names are part of the public contract — other modules subscribe to them.
export { ORDER_EVENTS };
export { createOrderService, createOrderRepository };

export const ordersPlugin = {
  name: 'orders',
  register({ app, db, eventBus, logger, requireAuth }) {
    const orderRepository = createOrderRepository({ db });
    const orderService = createOrderService({ orderRepository, eventBus, logger });

    // requireAuth populates req.auth from the session before any route runs.
    app.use('/orders', requireAuth, createOrderRoutes({ orderService }));

    // Expose the service interface for required cross-module calls.
    return { orderService };
  },
};

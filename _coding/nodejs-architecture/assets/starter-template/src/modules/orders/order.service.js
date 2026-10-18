// Business logic + access checks. Every method takes an `actor` — identity
// derived from the session ({ userId, orgId, role }), never from the client —
// and scopes its work to actor.orgId. See references/security-tenancy.md.
//
// Two mechanisms in one method:
//   - saving the order is REQUIRED  -> direct, awaited call
//   - reacting to the order         -> publish an event (optional reactions)

import { ORDER_EVENTS } from './order.events.js';

export function createOrderService({ orderRepository, eventBus, logger }) {
  return {
    // actor = { userId, orgId, role } from the session; input is validated.
    async createOrder(actor, input) {
      const order = await orderRepository.create(actor.orgId, input);

      logger.info('Order created', { orderId: order.id, orgId: actor.orgId });

      await eventBus.publish(ORDER_EVENTS.CREATED, {
        orderId: order.id,
        orgId: order.orgId,
        customerId: order.customerId,
        total: order.total,
      });

      return order;
    },

    async getOrder(actor, id) {
      // Org-scoped read: another org's id resolves to null (→ 404, not 403,
      // so we don't leak that the row exists).
      return orderRepository.findByIdForOrg(actor.orgId, id);
    },
  };
}

// Unit tests for the order service. Because the service takes its deps as
// arguments (dependency injection), we inject plain fakes — no mocking framework.
// This is the payoff of the ports/adapters design. See references/testing.md.

import { describe, it, expect } from 'vitest';
import { createOrderService } from './order.service.js';
import { createOrderRepository } from './order.repository.js';
import { createEventBus } from '../../infra/events/create-event-bus.js';

const silentLogger = { info: () => {}, warn: () => {}, error: () => {} };

function setup() {
  const db = { orders: [] };
  const orderRepository = createOrderRepository({ db });
  const published = [];
  const eventBus = createEventBus({ logger: silentLogger });
  eventBus.subscribe('order.created', (e) => published.push(e), { name: 'test.capture' });
  const service = createOrderService({ orderRepository, eventBus, logger: silentLogger });
  return { service, published };
}

const orgA = { userId: 'user_a', orgId: 'org_a', role: 'admin' };
const orgB = { userId: 'user_b', orgId: 'org_b', role: 'member' };

describe('order service', () => {
  it('creates an order scoped to the actor org and publishes order.created', async () => {
    const { service, published } = setup();

    const order = await service.createOrder(orgA, { customerId: 'cust_1', total: 42 });

    expect(order.orgId).toBe('org_a');
    expect(published).toHaveLength(1);
    expect(published[0]).toMatchObject({ orderId: order.id, orgId: 'org_a', total: 42 });
  });

  it('does not leak an order across orgs', async () => {
    const { service } = setup();

    const order = await service.createOrder(orgA, { customerId: 'cust_1', total: 42 });

    // Same id, different org → must not be found (would become a 404 upstream).
    expect(await service.getOrder(orgB, order.id)).toBeNull();
    // Owning org can read it.
    expect(await service.getOrder(orgA, order.id)).toMatchObject({ id: order.id });
  });
});

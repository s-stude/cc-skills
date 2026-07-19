// Event names + payload shapes this module owns and publishes.
// Other modules import these constants instead of hard-coding magic strings.

export const ORDER_EVENTS = {
  CREATED: 'order.created',
};

// order.created payload: { orderId, orgId, customerId, total }
// Carry orgId so subscribers stay org-scoped too.

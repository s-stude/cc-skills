// Persistence adapter. In a real app this is Knex + PostgreSQL (see
// references/database.md); here it's an in-memory array so the starter runs with
// no database. Either way every method is ORG-SCOPED and filters soft-deleted
// rows — defense in depth, so a service that forgot to check still can't leak
// across orgs. DB rows are snake_case; DTOs going out are camelCase.

import { generateShortUID } from '../../infra/id.js';

// OrderRepository socket (every method takes orgId):
//   create(orgId, input)        -> Promise<orderDto>
//   findByIdForOrg(orgId, id)   -> Promise<orderDto | null>
export function createOrderRepository({ db }) {
  const toDto = (row) => ({
    id: row.id,
    orgId: row.org_id,
    customerId: row.customer_id,
    total: row.total,
  });

  return {
    async create(orgId, input) {
      const row = {
        id: generateShortUID(),
        org_id: orgId,
        customer_id: input.customerId,
        total: input.total,
        is_deleted: false,
      };
      db.orders.push(row);
      return toDto(row);
    },

    async findByIdForOrg(orgId, id) {
      const row = db.orders.find(
        (o) => o.id === id && o.org_id === orgId && o.is_deleted === false,
      );
      return row ? toDto(row) : null;
    },
  };
}

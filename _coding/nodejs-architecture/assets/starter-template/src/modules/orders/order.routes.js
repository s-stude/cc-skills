// HTTP adapter. Validate untrusted input with Zod, pass the session-derived
// req.auth as the actor, and let the global error handler deal with throws.
// No business logic here — the route delegates. Identity comes from req.auth,
// never from the body.

import express from 'express';
import { z } from 'zod';

const createOrderSchema = z.object({
  customerId: z.string(),
  total: z.number().positive(),
});

export function createOrderRoutes({ orderService }) {
  const router = express.Router();

  router.post('/', async (req, res, next) => {
    try {
      const input = createOrderSchema.parse(req.body);
      const order = await orderService.createOrder(req.auth, input);
      res.status(201).json(order);
    } catch (error) {
      next(error);
    }
  });

  router.get('/:id', async (req, res, next) => {
    try {
      const order = await orderService.getOrder(req.auth, req.params.id);
      if (!order) return res.status(404).json({ error: 'Not found' });
      res.json(order);
    } catch (error) {
      next(error);
    }
  });

  return router;
}

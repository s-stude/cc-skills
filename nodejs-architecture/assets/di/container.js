// A tiny dependency-injection container for simple/medium Node.js apps.
// Lazy singletons, cycle detection, and pre-built values. No dependencies.
//
// Usage:
//   const c = createContainer();
//   c.value('config', loadConfig());
//   c.register('logger', (c) => createLogger({ level: c.resolve('config').logLevel }));
//   c.register('eventBus', (c) => createEventBus({ logger: c.resolve('logger') }));
//   const eventBus = c.resolve('eventBus'); // built once, cached
//
// A factory receives the container so it can resolve its own dependencies.
// Everything is a singleton within one container. For per-request instances,
// create a child scope with c.scope() or reach for Awilix.

export function createContainer() {
  const factories = new Map(); // name -> (container) => instance
  const instances = new Map(); // name -> built instance (cache)
  const building = new Set(); // names currently resolving (cycle detection)

  const container = {
    // Register a lazy singleton. The factory runs at most once, on first resolve.
    register(name, factory) {
      if (typeof factory !== 'function') {
        throw new TypeError(`Factory for "${name}" must be a function`);
      }
      factories.set(name, factory);
      return container;
    },

    // Register an already-built value (config object, db handle, etc.).
    value(name, instance) {
      instances.set(name, instance);
      return container;
    },

    // Build, or return the cached instance for, a name.
    resolve(name) {
      if (instances.has(name)) return instances.get(name);

      const factory = factories.get(name);
      if (!factory) {
        throw new Error(`Nothing registered for "${name}"`);
      }
      if (building.has(name)) {
        const cycle = [...building, name].join(' -> ');
        throw new Error(`Dependency cycle detected: ${cycle}`);
      }

      building.add(name);
      try {
        const instance = factory(container);
        instances.set(name, instance);
        return instance;
      } finally {
        building.delete(name);
      }
    },

    has(name) {
      return instances.has(name) || factories.has(name);
    },

    // A child scope inherits parent registrations but caches its own instances,
    // so resolving a name here builds it fresh — useful for per-request wiring.
    scope() {
      const child = createContainer();
      for (const [name, factory] of factories) child.register(name, factory);
      for (const [name, instance] of instances) child.value(name, instance);
      return child;
    },
  };

  return container;
}

// Fictional example for the learn-repo:module-dependency skill. Not a default architecture.
const PAGE = {
	kind: "module-dependency",
	eyebrow: "Example app · Modules",
	title: "Which modules the example app is made of, and what needs what",
	intro: "Four internal modules and one package. Orders and Storage depend on each other. Click a module for its dependencies and dependents, or use the trace buttons to see everything reachable.",
	sourceNote: "Built from a static import scan of the fictional <code>src/</code> on 2026-11-01, commit <code>abc1234</code>. Type-only imports are drawn separately."
};
const TYPES = {};
const EDGE_KINDS = {};
const VIEWS = [
	{
		id: "graph",
		notation: "graph",
		tab: "Module graph",
		title: "Module dependency graph",
		purpose: "What each module needs and who needs it.",
		read: "Follow an arrow from the module that needs something to the module it needs. Dashed boxes are outside packages; the dotted one could not be resolved.",
		scope: "src/ui, src/worker, src/orders, src/storage. Tests excluded.",
		nodes: [
			{ id: "ui", type: "module", label: "ui", sub: "src/ui", short: "Screens", col: 0, row: 0, ev: "code", refs: [ "src/ui/index.ts" ] },
			{ id: "worker", type: "module", label: "worker", sub: "src/worker", short: "Background jobs", col: 2, row: 0, ev: "code", refs: [ "src/worker/index.ts" ] },
			{ id: "orders", type: "module", label: "orders", sub: "src/orders", short: "Order rules and checkout", col: 1, row: 1, ev: "code", refs: [ "src/orders/index.ts" ] },
			{ id: "storage", type: "module", label: "storage", sub: "src/storage", short: "Saves and loads records", col: 1, row: 2, ev: "code", refs: [ "src/storage/index.ts" ] },
			{ id: "pg", type: "external", label: "pg", sub: "npm package", short: "PostgreSQL client", col: 0, row: 2, ev: "code", refs: [ "package.json:14" ] },
			{ id: "reports", type: "unresolved", label: "./legacy/reports", short: "Dynamic import; file not found", col: 2, row: 2, ev: "code", refs: [ "src/orders/export.ts:8" ] }
		],
		edges: [
			{ from: "ui", to: "orders", kind: "imports", label: "placeOrder", ev: "code+check", refs: [ "src/ui/checkout.tsx:3" ] },
			{ from: "worker", to: "orders", kind: "imports", label: "expireCarts", ev: "code", refs: [ "src/worker/carts.ts:2" ] },
			{ id: "orders-storage", from: "orders", to: "storage", kind: "imports", label: "saveOrder", ev: "code+check", refs: [ "src/orders/checkout.ts:5" ] },
			{ id: "storage-orders", from: "storage", to: "orders", kind: "type", label: "Order type", ev: "code+check", refs: [ "src/storage/orders.ts:1" ], detail: "A type-only import. It makes a cycle in the source graph but nothing from orders runs inside storage." },
			{ from: "storage", to: "pg", kind: "imports", label: "Pool", ev: "code", refs: [ "src/storage/db.ts:1" ] },
			{ from: "orders", to: "reports", kind: "runtime", label: "import() on export", ev: "code", refs: [ "src/orders/export.ts:8" ] }
		]
	},
	{
		id: "inside-orders",
		notation: "internals",
		module: "orders",
		parent: "graph",
		focus: "orders",
		tab: "Inside orders",
		title: "Inside the orders module",
		purpose: "What orders exposes, what it is made of, and which part crosses the boundary.",
		read: "The dashed boundary is the module. Only index.ts is public; arrows leaving the boundary are the module's dependencies.",
		groups: [ { id: "orders-boundary", label: "ORDERS (src/orders)", col: 0, row: 0, w: 2, h: 2 } ],
		nodes: [
			{ id: "index", type: "part", label: "index.ts", short: "Public surface: placeOrder, expireCarts", col: 0, row: 0, group: "orders-boundary", ev: "code+check", refs: [ "src/orders/index.ts:1-4" ] },
			{ id: "checkout", type: "part", label: "checkout.ts", short: "Validates the cart, saves the order", col: 1, row: 0, group: "orders-boundary", ev: "code", refs: [ "src/orders/checkout.ts" ] },
			{ id: "carts", type: "part", label: "carts.ts", short: "Finds and expires old carts", col: 0, row: 1, group: "orders-boundary", ev: "code", refs: [ "src/orders/carts.ts" ] },
			{ id: "order-type", type: "contract", label: "Order", sub: "type", short: "Shape of a saved order", col: 1, row: 1, group: "orders-boundary", ev: "code", refs: [ "src/orders/types.ts:3" ] },
			{ id: "storage", type: "module", label: "storage", sub: "src/storage", col: 2, row: 0, ev: "code" }
		],
		edges: [
			{ from: "index", to: "checkout", kind: "imports", label: "re-exports", ev: "code+check", refs: [ "src/orders/index.ts:2" ] },
			{ from: "index", to: "carts", kind: "imports", label: "re-exports", ev: "code+check", refs: [ "src/orders/index.ts:3" ] },
			{ from: "checkout", to: "order-type", kind: "type", label: "Order", ev: "code", refs: [ "src/orders/checkout.ts:2" ] },
			{ from: "checkout", to: "storage", kind: "imports", label: "saveOrder", ev: "code+check", refs: [ "src/orders/checkout.ts:5" ] }
		]
	}
];
const TOUR = [
	{ view: "graph", nodes: [ "ui", "orders" ], edges: [ "e0" ], text: "Read the arrow as “ui depends on orders”: ui imports placeOrder from it." },
	{ view: "graph", nodes: [ "orders", "storage" ], edges: [ "orders-storage", "storage-orders" ], text: "Orders and storage depend on each other. The storage → orders edge is type-only, so the cycle exists for the compiler but not at runtime." },
	{ view: "inside-orders", nodes: [ "checkout", "storage" ], edges: [ "e3" ], text: "Inside orders, only checkout.ts crosses the boundary to storage." }
];
const QUIZ = [
	{ q: "If storage changes its saveOrder signature, which modules may need review?", a: "orders directly, then ui and worker through orders. That is a review scope, not a guarantee they break." },
	{ q: "Does ui depend on storage?", a: "Not directly. It reaches storage only through orders." }
];
const GLOSSARY = [
	[ "Dependency", "A module this one needs. Outgoing arrow." ],
	[ "Dependent", "A module that needs this one. Incoming arrow." ],
	[ "Cycle", "Following arrows leads back to the start." ]
];
const SOURCES = [
	{ label: "Bazel: dependencies", href: "https://bazel.build/concepts/dependencies" }
];
const NOTES = "";

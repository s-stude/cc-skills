// Fictional example for the learn-repo:c4-model skill. Not a default architecture.
const PAGE = {
	kind: "c4",
	eyebrow: "Example shop · Architecture",
	title: "How the example shop is built, from context to components",
	intro: "A shopper uses a browser shop that calls an order API backed by a database. Start at L1 and zoom in. Click any box or arrow for its details, evidence and the other views it appears in.",
	sourceNote: "Built from the fictional brief in <code>brief.md</code> on 2026-11-01. Every element is marked with where its evidence came from."
};
const TYPES = {};
const EDGE_KINDS = {};
const VIEWS = [
	{
		id: "l1",
		level: "L1",
		tab: "L1 Context",
		title: "Shop system context",
		purpose: "Who uses the shop and which outside systems it talks to.",
		read: "One focal system in blue. People and outside systems around it. Arrows read as “uses”.",
		nodes: [
			{ id: "shopper", type: "person", label: "Shopper", short: "Browses products and places orders", col: 0, row: 0, ev: "docs", refs: [ "brief.md §1" ], detail: "Anyone buying from the shop. No accounts are mentioned in the brief." },
			{ id: "shop", type: "system", label: "Shop", short: "Sells products online", col: 1, row: 0, ev: "docs", refs: [ "brief.md §1" ], detail: "The software system this page explains." },
			{ id: "payment-provider", type: "external-system", label: "Payment provider", short: "Charges cards", col: 2, row: 0, ev: "docs", refs: [ "brief.md §3" ], detail: "Third-party payment service. Its name is not given in the brief." }
		],
		edges: [
			{ from: "shopper", to: "shop", kind: "uses", label: "Places orders", ev: "docs", refs: [ "brief.md §1" ] },
			{ from: "shop", to: "payment-provider", kind: "uses", label: "Requests payments", ev: "docs", refs: [ "brief.md §3" ] }
		]
	},
	{
		id: "l2",
		level: "L2",
		tab: "L2 Containers",
		title: "Containers inside the shop",
		parent: "l1",
		focus: "shop",
		purpose: "The applications and data stores that make up the shop.",
		read: "The dashed boundary is the shop. A container is an application or a data store, not a Docker container.",
		groups: [ { id: "shop-boundary", label: "SHOP", col: 0, row: 1, w: 2, h: 2 } ],
		nodes: [
			{ id: "shopper", type: "person", label: "Shopper", short: "Browses products and places orders", col: 0, row: 0, ev: "docs", refs: [ "brief.md §1" ] },
			{ id: "browser", type: "container", label: "Browser shop", sub: "[Container: React SPA]", short: "Product pages and checkout UI", col: 0, row: 1, group: "shop-boundary", ev: "docs", refs: [ "brief.md §2" ], detail: "Single-page app served as static files." },
			{ id: "order-api", type: "container", label: "Order API", sub: "[Container: Node.js]", short: "Takes orders and payments", col: 1, row: 1, group: "shop-boundary", ev: "docs", refs: [ "brief.md §2" ], detail: "The only container that writes orders." },
			{ id: "orders-db", type: "database", label: "Orders DB", sub: "[Container: PostgreSQL]", short: "Orders and their lines", col: 1, row: 2, group: "shop-boundary", ev: "docs", refs: [ "brief.md §2" ] },
			{ id: "payment-provider", type: "external-system", label: "Payment provider", short: "Charges cards", col: 2, row: 1, ev: "docs", refs: [ "brief.md §3" ] }
		],
		edges: [
			{ from: "shopper", to: "browser", kind: "uses", label: "Browses, checks out", ev: "docs" },
			{ from: "browser", to: "order-api", kind: "uses", label: "Submits orders [JSON/HTTPS]", ev: "docs", refs: [ "brief.md §2" ] },
			{ from: "order-api", to: "orders-db", kind: "uses", label: "Reads/writes orders [SQL]", ev: "docs", refs: [ "brief.md §2" ] },
			{ from: "order-api", to: "payment-provider", kind: "uses", label: "Creates payments [HTTPS]", ev: "inferred", detail: "The brief says the shop pays through the provider; that the Order API makes the call is inferred from it being the only back-end container." }
		]
	},
	{
		id: "l3",
		level: "L3",
		tab: "L3 Components",
		title: "Components of the Order API",
		parent: "l2",
		focus: "order-api",
		purpose: "What the Order API is made of and which component talks to what.",
		read: "The boundary is the Order API container. Boxes outside it are the containers and systems it talks to.",
		groups: [ { id: "api-boundary", label: "ORDER API", col: 0, row: 1, w: 3, h: 2 } ],
		nodes: [
			{ id: "browser", type: "container", label: "Browser shop", sub: "[Container: React SPA]", col: 0, row: 0, ev: "docs" },
			{ id: "checkout", type: "component", label: "Checkout", short: "Validates the cart and creates the order", col: 0, row: 1, group: "api-boundary", ev: "docs", refs: [ "brief.md §4" ], detail: "Entry point for POST /orders." },
			{ id: "payment-adapter", type: "component", label: "Payment adapter", short: "Wraps the provider's API", col: 2, row: 1, group: "api-boundary", ev: "docs", refs: [ "brief.md §4" ] },
			{ id: "order-repository", type: "component", label: "Order repository", short: "Saves and loads orders", col: 1, row: 2, group: "api-boundary", ev: "inferred", detail: "The brief names checkout and the payment adapter only; a persistence component is inferred from the database link." },
			{ id: "orders-db", type: "database", label: "Orders DB", sub: "[Container: PostgreSQL]", col: 1, row: 3, ev: "docs" },
			{ id: "payment-provider", type: "external-system", label: "Payment provider", short: "Charges cards", col: 3, row: 1, ev: "docs" }
		],
		edges: [
			{ id: "submit", from: "browser", to: "checkout", kind: "uses", label: "Submits orders [JSON/HTTPS]", ev: "docs" },
			{ id: "pay", from: "checkout", to: "payment-adapter", kind: "uses", label: "Requests payment", ev: "docs", refs: [ "brief.md §4" ] },
			{ id: "save", from: "checkout", to: "order-repository", kind: "uses", label: "Saves the order", ev: "inferred" },
			{ from: "order-repository", to: "orders-db", kind: "uses", label: "SQL", ev: "inferred" },
			{ id: "charge", from: "payment-adapter", to: "payment-provider", kind: "uses", label: "Creates payment [HTTPS]", ev: "docs" }
		]
	},
	{
		id: "l4",
		level: "L4",
		tab: "L4 Code",
		title: "Code inside Checkout",
		parent: "l3",
		focus: "checkout",
		purpose: "The classes or functions that implement Checkout.",
		read: "Would show code elements of one component.",
		nodes: [],
		edges: [],
		gap: "The brief names no classes, functions or files for Checkout. Point the skill at the source or a design note to fill this level."
	},
	{
		id: "uml",
		level: "UML",
		tab: "UML components",
		title: "Checkout and payment contracts",
		purpose: "Which interfaces each component provides and requires.",
		read: "A circle is a provided interface, a half circle a required one. The ball-and-socket on a line joins a requirement to a provider; it is not a call direction.",
		nodes: [
			{ id: "checkout", type: "uml-component", label: "Checkout", provides: [ "ICheckout" ], requires: [ "IPayments" ], col: 0, row: 0, ev: "docs", refs: [ "brief.md §4" ] },
			{ id: "payment-adapter", type: "uml-component", label: "Payment adapter", provides: [ "IPayments" ], col: 2, row: 0, ev: "docs", refs: [ "brief.md §4" ] },
			{ id: "order-repository", type: "uml-component", label: "Order repository", col: 0, row: 1, ev: "inferred" }
		],
		edges: [
			{ from: "checkout", to: "payment-adapter", kind: "assembly", label: "IPayments", ev: "docs", refs: [ "brief.md §4" ] },
			{ from: "checkout", to: "order-repository", kind: "dependency", label: "«use»", ev: "inferred" }
		]
	}
];
const TOUR = [
	{ view: "l1", nodes: [ "shopper", "shop" ], edges: [ "e0" ], text: "Start with who uses the system. The shopper places orders with the shop; everything else is inside that one box for now." },
	{ view: "l2", nodes: [ "browser", "order-api", "orders-db" ], edges: [ "e1", "e2" ], text: "Inside the shop: the browser app sends orders to the Order API, which is the only container that writes to the database." },
	{ view: "l3", nodes: [ "checkout", "payment-adapter", "payment-provider" ], edges: [ "pay", "charge" ], text: "Inside the Order API, Checkout asks the Payment adapter to charge; only the adapter knows the provider's API." }
];
const QUIZ = [
	{ q: "Is the Order repository a fact from the brief?", a: "No. It is marked [inferred]: the brief names Checkout and the Payment adapter only, and the database link suggests a persistence component." },
	{ q: "Why is the L4 tab empty?", a: "The brief names no code elements. The view states the gap instead of inventing classes." }
];
const GLOSSARY = [
	[ "Container (C4)", "An application or data store that runs on its own. Not a Docker container." ],
	[ "Component (C4)", "A group of related code behind an interface inside one container." ],
	[ "Provided / required interface", "UML notation: a circle the component offers, a half circle it needs from another component." ]
];
const SOURCES = [
	{ label: "C4 model: diagrams", href: "https://c4model.com/diagrams" },
	{ label: "brief.md (fictional)", note: "the only input for this example" }
];
const NOTES = "";

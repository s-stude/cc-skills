// Fictional example for the learn-repo:data-flow skill. Not a default architecture.
const PAGE = {
	kind: "data-flow",
	eyebrow: "Example analytics · Daily sales",
	title: "Where the daily sales total comes from",
	intro: "Order lines leave the order system, get validated, turn into amounts and are summed per day for a dashboard. The same scenario is shown three ways: a DFD, a lineage graph and the ETL pipeline. Click any box or arrow for details.",
	sourceNote: "Built from the fictional notes in <code>analytics-notes.md</code> and <code>daily_sales.sql</code> on 2026-11-01."
};
const TYPES = {};
const EDGE_KINDS = {};
const VIEWS = [
	{
		id: "dfd-context",
		notation: "dfd",
		level: "context",
		tab: "DFD",
		title: "Context: the analytics service as one process",
		purpose: "What data crosses the boundary of the analytics service.",
		read: "Rectangles are external entities, the rounded box is the whole service. Arrows carry named data, not calls or timing.",
		nodes: [
			{ id: "order-system", type: "entity", label: "Order system", short: "Sends order lines", col: 0, row: 0, ev: "docs", refs: [ "analytics-notes.md §1" ], detail: "Owned by another team. Outside the boundary." },
			{ id: "analytics", type: "process", label: "Analytics service", short: "Turns order lines into daily totals", col: 1, row: 0, ev: "docs", refs: [ "analytics-notes.md §1" ] },
			{ id: "dashboard", type: "entity", label: "Sales dashboard", short: "Shows totals per day", col: 2, row: 0, ev: "docs", refs: [ "analytics-notes.md §4" ] },
			{ id: "steward", type: "entity", label: "Data steward", short: "Reviews rejected lines", col: 1, row: 1, ev: "docs", refs: [ "analytics-notes.md §2" ] }
		],
		edges: [
			{ from: "order-system", to: "analytics", kind: "flow", label: "order line records", ev: "docs" },
			{ from: "analytics", to: "dashboard", kind: "flow", label: "daily totals", ev: "docs" },
			{ from: "analytics", to: "steward", kind: "flow", label: "rejected lines", ev: "docs" }
		]
	},
	{
		id: "dfd-inside",
		notation: "dfd",
		level: "decomposition",
		tab: "DFD",
		parent: "dfd-context",
		focus: "analytics",
		title: "Decomposition: inside the analytics service",
		purpose: "Which processes change the data and where it is kept.",
		read: "The open-ended box is a data store. Every flow touches a process; the boundary flows match the context view above.",
		nodes: [
			{ id: "order-system", type: "entity", label: "Order system", col: 0, row: 0, ev: "docs" },
			{ id: "validate", type: "process", label: "Validate lines", short: "Drop lines with quantity ≤ 0 or no price", col: 1, row: 0, ev: "code", refs: [ "daily_sales.sql:12" ] },
			{ id: "calculate", type: "process", label: "Calculate daily sales", short: "quantity × unit price, summed per day", col: 2, row: 0, ev: "code", refs: [ "daily_sales.sql:20-31" ] },
			{ id: "daily-sales", type: "store", label: "daily_sales", short: "One row per day", col: 3, row: 0, ev: "code", refs: [ "daily_sales.sql:3" ] },
			{ id: "serve", type: "process", label: "Serve totals", short: "Reads totals for the dashboard", col: 3, row: 1, ev: "inferred", detail: "The notes say the dashboard reads daily totals; the API in between is not described." },
			{ id: "dashboard", type: "entity", label: "Sales dashboard", col: 2, row: 1, ev: "docs" },
			{ id: "steward", type: "entity", label: "Data steward", col: 1, row: 1, ev: "docs" }
		],
		edges: [
			{ from: "order-system", to: "validate", kind: "flow", label: "order line records", ev: "docs" },
			{ from: "validate", to: "calculate", kind: "flow", label: "valid lines", ev: "code", refs: [ "daily_sales.sql:12" ] },
			{ from: "validate", to: "steward", kind: "flow", label: "rejected lines", ev: "docs" },
			{ from: "calculate", to: "daily-sales", kind: "flow", label: "daily total rows", ev: "code", refs: [ "daily_sales.sql:31" ] },
			{ from: "daily-sales", to: "serve", kind: "flow", label: "stored totals", ev: "inferred" },
			{ from: "serve", to: "dashboard", kind: "flow", label: "daily totals", ev: "inferred" }
		]
	},
	{
		id: "lineage",
		notation: "lineage",
		tab: "Lineage",
		title: "Lineage of daily_sales.total",
		purpose: "Which datasets the dashboard number comes from, and what depends on order_lines.",
		read: "Datasets are cylinders, the job that derives one from another is a hexagon. Click a dataset and use Upstream or Downstream.",
		nodes: [
			{ id: "order-lines", type: "dataset", label: "order_lines", sub: "orders_db.public", col: 0, row: 0, ev: "code", refs: [ "daily_sales.sql:14" ], detail: "Fields used: order_date (grouping), quantity and unit_price (value), status (filter)." },
			{ id: "job", type: "job", label: "daily_sales job", short: "Validate, multiply, sum per day", col: 1, row: 0, ev: "code", refs: [ "daily_sales.sql" ] },
			{ id: "daily-sales", type: "dataset", label: "daily_sales", sub: "analytics.public", col: 2, row: 0, ev: "code", refs: [ "daily_sales.sql:3" ], detail: "total = SUM(quantity * unit_price) grouped by order_date. Each row aggregates many order lines." },
			{ id: "dashboard", type: "consumer", label: "Sales dashboard", col: 3, row: 0, ev: "docs" }
		],
		edges: [
			{ from: "order-lines", to: "job", kind: "derives", label: "read", ev: "code", refs: [ "daily_sales.sql:14" ] },
			{ from: "job", to: "daily-sales", kind: "derives", label: "write (replace day)", ev: "code", refs: [ "daily_sales.sql:31" ] },
			{ from: "daily-sales", to: "dashboard", kind: "derives", label: "read", ev: "docs" }
		]
	},
	{
		id: "pipeline",
		notation: "pipeline",
		pipeline: "ETL",
		tab: "ETL pipeline",
		title: "The nightly ETL run",
		purpose: "How the data is extracted, transformed and loaded, in order.",
		read: "Rounded boxes are stages, cylinders are datasets. The dotted arrow from the scheduler starts the run and carries no data. This is ETL: the transformation happens before loading into the analytics target.",
		nodes: [
			{ id: "order-lines", type: "dataset", label: "order_lines", sub: "source", col: 0, row: 0, ev: "code", refs: [ "daily_sales.sql:14" ] },
			{ id: "extract", type: "stage", label: "Extract", short: "Lines changed since the last run", col: 1, row: 0, ev: "docs", refs: [ "analytics-notes.md §3" ] },
			{ id: "validate-stage", type: "stage", label: "Validate", short: "Reject bad quantity or price", col: 2, row: 0, ev: "code", refs: [ "daily_sales.sql:12" ] },
			{ id: "aggregate", type: "stage", label: "Calculate and aggregate", short: "Amount per line, sum per day", col: 3, row: 0, ev: "code", refs: [ "daily_sales.sql:20-31" ] },
			{ id: "load", type: "stage", label: "Load", short: "Replace the affected days", col: 4, row: 0, ev: "code", refs: [ "daily_sales.sql:31" ] },
			{ id: "daily-sales", type: "dataset", label: "daily_sales", sub: "target", col: 4, row: 1, ev: "code" },
			{ id: "quarantine", type: "artifact", label: "rejected_lines", sub: "quarantine file", short: "Lines a steward reviews", col: 2, row: 1, ev: "docs", refs: [ "analytics-notes.md §2" ] },
			{ id: "scheduler", type: "scheduler", label: "Nightly schedule", short: "02:00 UTC", col: 1, row: 1, ev: "docs", refs: [ "analytics-notes.md §3" ] }
		],
		edges: [
			{ from: "order-lines", to: "extract", kind: "data", label: "changed lines", ev: "docs" },
			{ from: "extract", to: "validate-stage", kind: "data", label: "raw lines", ev: "docs" },
			{ from: "validate-stage", to: "aggregate", kind: "data", label: "valid lines", ev: "code", refs: [ "daily_sales.sql:12" ] },
			{ from: "validate-stage", to: "quarantine", kind: "data", label: "rejected lines", ev: "docs" },
			{ from: "aggregate", to: "load", kind: "data", label: "daily totals", ev: "code", refs: [ "daily_sales.sql:20-31" ] },
			{ from: "load", to: "daily-sales", kind: "data", label: "upsert by day", ev: "code", refs: [ "daily_sales.sql:31" ] },
			{ from: "scheduler", to: "extract", kind: "trigger", label: "starts", ev: "docs" }
		]
	}
];
const TOUR = [
	{ view: "dfd-context", nodes: [ "order-system", "analytics", "dashboard" ], edges: [ "e0", "e1" ], text: "Seen from outside, order lines go in and daily totals come out." },
	{ view: "dfd-inside", nodes: [ "validate", "steward" ], edges: [ "e1", "e2" ], text: "Validation splits the input: valid lines go on, rejected lines go to the data steward." },
	{ view: "lineage", nodes: [ "order-lines", "job", "daily-sales" ], edges: [ "e0", "e1" ], text: "The dashboard total is derived from order_lines through one job. Each total row sums many lines." }
];
const QUIZ = [
	{ q: "A line has quantity 2 and unit price 15. What does it add to its day's total?", a: "30. It contributes to the aggregate; the total is the sum of all valid lines that day." },
	{ q: "Is this ETL or ELT?", a: "ETL: lines are validated and summed before anything is loaded into the analytics target." }
];
const GLOSSARY = [
	[ "Data flow", "Named data moving between an entity, a process or a store. Not a call and not a timing." ],
	[ "Lineage", "Which inputs an output is derived from, through which job." ],
	[ "ETL / ELT", "Transform before loading into the target, or load first and transform inside it." ]
];
const SOURCES = [
	{ label: "IBM: data flow diagrams", href: "https://www.ibm.com/think/topics/data-flow-diagram" },
	{ label: "OpenLineage object model", href: "https://openlineage.io/docs/spec/object-model/" }
];
const NOTES = `<h2>One line through the pipeline</h2>
<table><thead><tr><th>Stage</th><th>Record (illustrative)</th></tr></thead><tbody>
<tr><td>order_lines</td><td><code>{ order_date: 2026-10-31, quantity: 2, unit_price: 15 }</code></td></tr>
<tr><td>Calculate</td><td><code>amount = 30</code></td></tr>
<tr><td>daily_sales</td><td><code>{ day: 2026-10-31, total: 30 + every other valid line that day }</code></td></tr>
</tbody></table>`;

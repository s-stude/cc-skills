// Fictional example for the learn-repo:data-model skill. Not a default architecture.
const PAGE = {
	kind: "data-model",
	eyebrow: "Example library · Data model",
	title: "How the library keeps track of books, copies and loans",
	intro: "A library owns several copies of each book and lends copies to members. The same model is shown at three abstraction levels and in two notations. Click an entity or a relationship to see its rule, evidence and counterparts in other views.",
	sourceNote: "Built from the fictional <code>schema.sql</code> and <code>domain.ts</code> on 2026-11-01. Rules not enforced by the schema are marked."
};
const TYPES = {};
const EDGE_KINDS = {};
const VIEWS = [
	{
		id: "conceptual",
		level: "conceptual",
		notation: "concept",
		tab: "Conceptual",
		title: "Business concepts",
		purpose: "What the library talks about, without keys or storage.",
		read: "Read each line both ways. The number next to a concept is how many of it relate to one instance at the other end.",
		nodes: [
			{ id: "member", key: "member", type: "concept", label: "Member", short: "A person allowed to borrow", col: 0, row: 0, ev: "docs", refs: [ "rules.md §1" ] },
			{ id: "loan", key: "loan", type: "concept", label: "Loan", short: "One copy lent to one member for a period", col: 1, row: 0, ev: "docs", refs: [ "rules.md §2" ] },
			{ id: "copy", key: "copy", type: "concept", label: "Book copy", short: "A physical item on a shelf", col: 2, row: 0, ev: "docs" },
			{ id: "book", key: "book", type: "concept", label: "Book", short: "A title, independent of copies", col: 2, row: 1, ev: "docs" }
		],
		edges: [
			{ from: "member", to: "loan", kind: "relates", label: "borrows", fromEnd: "1", toEnd: "0..*", ev: "docs", refs: [ "rules.md §2" ] },
			{ from: "loan", to: "copy", kind: "relates", label: "of", fromEnd: "0..*", toEnd: "1", ev: "docs" },
			{ from: "book", to: "copy", kind: "relates", label: "has", fromEnd: "1", toEnd: "1..*", ev: "docs", detail: "“Every book has at least one copy” is a business rule; the schema does not enforce it." }
		]
	},
	{
		id: "physical",
		level: "physical",
		notation: "erd",
		tab: "Physical ERD",
		title: "Tables in PostgreSQL",
		purpose: "How the schema stores the concepts and which rules it enforces.",
		read: "Crow's foot notation: a bar is one, a circle is zero, the fork is many. The mark nearest a table counts rows of that table. A dashed line is a non-identifying relationship.",
		nodes: [
			{ id: "members", key: "member", type: "table", label: "Member", sub: "members", members: [ "PK id  bigint", "name  text NOT NULL", "email  text UNIQUE" ], col: 0, row: 0, h: 2, ev: "code+check", refs: [ "schema.sql:1-5" ] },
			{ id: "loans", key: "loan", type: "table", label: "Loan", sub: "loans", members: [ "PK id  bigint", "FK member_id  NOT NULL", "FK copy_id  NOT NULL", "starts_on  date", "returned_on  date NULL" ], col: 1, row: 0, h: 2, ev: "code+check", refs: [ "schema.sql:14-21" ], detail: "Nothing stops two open loans for one copy: there is no partial unique index on copy_id where returned_on is null." },
			{ id: "copies", key: "copy", type: "table", label: "Book copy", sub: "copies", members: [ "PK id  bigint", "FK book_id  NOT NULL", "barcode  text UNIQUE" ], col: 2, row: 0, h: 2, ev: "code+check", refs: [ "schema.sql:9-12" ] },
			{ id: "books", key: "book", type: "table", label: "Book", sub: "books", members: [ "PK id  bigint", "title  text NOT NULL", "isbn  text" ], col: 3, row: 0, h: 2, ev: "code", refs: [ "schema.sql:6-8" ] }
		],
		edges: [
			{ from: "members", to: "loans", kind: "erd-weak", label: "member_id", fromEnd: "1", toEnd: "0..*", ev: "code+check", refs: [ "schema.sql:16" ] },
			{ from: "loans", to: "copies", kind: "erd-weak", label: "copy_id", fromEnd: "0..*", toEnd: "1", ev: "code+check", refs: [ "schema.sql:17" ] },
			{ from: "copies", to: "books", kind: "erd-weak", label: "book_id", fromEnd: "0..*", toEnd: "1", ev: "code", refs: [ "schema.sql:10" ], detail: "The schema allows a book with zero copies, so the end at copies is 0..*, not the business rule's 1..*." }
		]
	},
	{
		id: "logical",
		level: "logical",
		notation: "uml",
		tab: "UML classes",
		title: "Domain classes in domain.ts",
		purpose: "How the code represents the same concepts.",
		read: "UML class notation. A filled diamond is composition: the part lives and dies with the whole. Numbers at line ends are multiplicities.",
		nodes: [
			{ id: "member", key: "member", type: "class", label: "Member", members: [ "id : string", "name : string", "address : Address" ], col: 0, row: 0, h: 2, ev: "code", refs: [ "domain.ts:3-8" ] },
			{ id: "address", type: "value", label: "Address", members: [ "street : string", "city : string" ], col: 0, row: 2, ev: "code", refs: [ "domain.ts:10" ], detail: "Embedded value. In the schema it is not stored at all yet." },
			{ id: "loan", key: "loan", type: "class", label: "Loan", members: [ "startsOn : Date", "returnedOn? : Date" ], ops: [ "isOpen() : boolean" ], col: 1, row: 0, h: 2, ev: "code", refs: [ "domain.ts:12-20" ] },
			{ id: "copy", key: "copy", type: "class", label: "Book copy", members: [ "barcode : string" ], col: 2, row: 0, ev: "code", refs: [ "domain.ts:22" ] }
		],
		edges: [
			{ from: "member", to: "address", kind: "composition", label: "address", fromEnd: "1", toEnd: "1", ev: "code", refs: [ "domain.ts:7" ] },
			{ from: "loan", to: "member", kind: "navigable", label: "member", fromEnd: "0..*", toEnd: "1", ev: "code", refs: [ "domain.ts:13" ] },
			{ from: "loan", to: "copy", kind: "navigable", label: "copy", fromEnd: "0..*", toEnd: "1", ev: "code", refs: [ "domain.ts:14" ] }
		]
	}
];
const TOUR = [
	{ view: "conceptual", nodes: [ "member", "loan" ], edges: [ "e0" ], text: "Read it both ways: each loan belongs to exactly one member; a member has zero or more loans." },
	{ view: "physical", nodes: [ "loans", "copies" ], edges: [ "e1" ], text: "In the schema the same rule is a NOT NULL foreign key copy_id. It does not limit a copy to one open loan." }
];
const QUIZ = [
	{ q: "Can a book exist with no copies in the database?", a: "Yes. The business rule says at least one, but copies.book_id only requires each copy to have a book." },
	{ q: "Why is Address not a table?", a: "It is an embedded value type in the code and is not stored in the schema yet." }
];
const GLOSSARY = [
	[ "Cardinality", "How many instances at one end relate to one instance at the other." ],
	[ "Composition", "A whole owns its parts; a part belongs to one whole." ]
];
const SOURCES = [
	{ label: "PostgreSQL: constraints", href: "https://www.postgresql.org/docs/18/ddl-constraints.html" }
];
const NOTES = "";

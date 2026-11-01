# Modeling semantics and teaching choices

## Levels and notation

Conceptual models describe business concepts and relationships. Logical models add attributes, identifiers, domains, and rules without choosing a DBMS implementation. Physical models specify storage structures, concrete types, and implementation constraints. Detail conventions vary; state the convention used in the lesson. [IBM: Data modeling](https://www.ibm.com/think/topics/data-modeling)

An entity–relationship diagram (ERD) depicts entity types, attributes where relevant, and relationships. It can communicate different levels of detail. Distinguish a type, such as Customer, from an individual instance. ERDs describe structure rather than execution order or data movement. [IBM: Entity relationship diagrams](https://www.ibm.com/think/topics/entity-relationship-diagram)

A UML class diagram describes static structure using classes/types, attributes, optional operations, and relationships. It can describe a domain without claiming the classes exist in code. A class is not automatically a database table. [IBM: UML class diagrams](https://developer.ibm.com/articles/the-class-diagram/)

Apply these distinctions to the user's evidence. A conceptual Order can map to several tables; an embedded Address can be a domain type without its own table. Explain mappings instead of forcing matching boxes in every view.

## ERD and relationship reading

The template draws Crow's Foot ERDs (`erd`, `erd-weak` edges with `fromEnd`/`toEnd`) and text multiplicities for conceptual and UML edges. If the audience knows Chen notation, say in the view's `read` text how the two map.

In Crow's Foot, a circle means zero, a bar means one, and the branching foot means many. Combine minimum and maximum at each endpoint. Write both readings before drawing: “Each Loan references exactly one BookCopy; a BookCopy can have zero or more Loans.” So the edge from BookCopy to Loan gets `fromEnd: "1"` and `toEnd: "0..*"`. The count at an end describes how many instances of that end relate to one instance at the opposite end. [IBM: Entity relationship diagrams](https://www.ibm.com/think/topics/entity-relationship-diagram)

“At most one active loan per copy” differs from “at most one loan ever.” Show temporal conditions explicitly. Do not convert unknown counts into `0..*`; that asserts a rule.

For relational logical models, resolve many-to-many relationships through associative entities when appropriate and explain attributes belonging to the association. A conceptual view may retain a direct many-to-many relationship. Do not impose pair uniqueness when repeated associations are legitimate events.

Distinguish identifying relationships, where parent identity participates in child identity (`erd`, solid line), from references that are only mandatory (`erd-weak`, dashed line). The line style means exactly that; confidence goes in `ev` and optionality in the end counts.

## Physical constraints versus business rules

Label relational PK, FK, and unique keys; show composite keys as groups. Primary keys are unique and non-null. Foreign keys enforce references, while nullability and uniqueness further restrict relationships. Null handling and constraint details can differ across databases. [PostgreSQL: Constraints](https://www.postgresql.org/docs/18/ddl-constraints.html)

Test schema explanations against counterexamples:

- A non-null child FK requires a parent for each child; it does not require every parent to have a child.
- An FK alone does not make a relationship one-to-one; check uniqueness on the referencing side.
- “Every order has items” may be a business rule unenforced by the shown table constraints. Distinguish intent from DB enforcement.
- An ORM association or application check is not proof of a database constraint. A performance index is not automatically a uniqueness rule.

Show DBMS types, defaults, indexes, referential actions, or partitions only when evidenced or explicitly proposed. Explain relevant choices without overwhelming the lesson with unrelated DDL. Consult the target database's documentation for dialect-sensitive behavior instead of generalizing PostgreSQL examples.

## UML class notation

Class nodes have compartments for name, `members` (attributes) and `ops` (operations). Typical UML notation is `name : Type` and `operation(parameter : Type) : ReturnType`. Leave out unsupported operations. [IBM: UML class diagrams](https://developer.ibm.com/articles/the-class-diagram/)

| Relationship | Notation |
| --- | --- |
| Association | `association`: solid line, multiplicities at ends. `navigable` adds an open arrow toward the referenced class; it does not indicate data flow. |
| Generalization | `generalization`: solid line, hollow triangle toward the superclass. |
| Realization | `realization`: dashed line, hollow triangle toward the interface. |
| Dependency | `dependency`: dashed open arrow toward the element depended on. |
| Shared aggregation | `aggregation` from the whole to the part: hollow diamond at the whole. |
| Composition | `composition` from the whole to the part: filled diamond at the whole. |

Use `1`, `0..1`, `0..*`, and `1..*` for multiplicities. Visibility, when needed, uses `+` public, `-` private, `#` protected, and `~` package, written at the start of the member line.

Composition expresses strong whole–part ownership; a part belongs to at most one composite at a time. Do not infer it from an FK or cascade-delete option alone. Prefer association when ownership is unknown. Explain the domain meaning if using shared aggregation. [IBM: UML aggregation and composition](https://developer.ibm.com/articles/the-class-diagram/)

The normative reference is [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1). Consult it for advanced semantics.

## Sources in the generated lesson

References researched on 2026-11-01. Put modeling sources for definitions and the user's documents or repository for domain facts in `SOURCES`. A notation reference does not substantiate a claim about the user's application.

# Diagram semantics

Research checked on 2026-11-01. These are modeling rules; the shared template fixes layout, shapes and colours. Consult the linked primary sources for unfamiliar notation rather than guessing.

## C4 scope ladder

| View | Scope and primary elements | Supporting context | Avoid |
| --- | --- | --- | --- |
| L1 — System context | One focal software system shown as a whole | People/roles and directly interacting external systems; business relationships | Internal services, classes, database internals, deployment topology |
| L2 — Containers | Applications and data stores inside that system; responsibilities and known technologies | Relevant people and external systems; labeled communications | Treating every folder or Docker image as a C4 container |
| L3 — Components | Functional components within one selected container | Directly connected containers, people, and external systems | Mixing internals of many containers into one unscoped view |
| L4 — Code | Implementation elements within one selected component: classes, interfaces, functions, objects, or tables | Relevant external code dependencies, clearly distinguished | Renaming the L3 boxes and calling the result code-level detail |

Sources: Simon Brown's [system context](https://c4model.com/diagrams/system-context), [container](https://c4model.com/diagrams/container), [component](https://c4model.com/diagrams/component), and [code](https://c4model.com/diagrams/code) definitions.

A C4 container means an application or data store, not necessarily a Docker container. A C4 component groups related functionality behind an interface within a container; it is not independently deployable. Folder/package boundaries are clues, not automatic component boundaries. See the official [container](https://c4model.com/abstractions/container) and [component](https://c4model.com/abstractions/component) abstractions.

Use UML class notation at L4 when it fits the language; use functions/modules or an appropriate data model otherwise. Include only implementation details that explain the architecture. C4 itself does not require every level for every project; this skill's default includes all requested levels but must acknowledge unavailable detail. See [C4 diagram selection](https://c4model.com/diagrams).

## C4 visual notation

Label elements with their name and responsibility (`short`); put known technology in `sub`, e.g. `[Container: Node.js]`. Label directed relationships with concrete intent, such as “Submits orders,” and add known protocols at container level. Use separate arrows when opposing directions have different meanings. Unknown protocols remain unknown. See [C4 notation](https://c4model.com/diagrams/notation).

Keep a static dependency distinct from a runtime sequence. For example, “Order service depends on Payment gateway” and “Gateway sends a payment event to Worker” are different relationships. Neither arrow's position establishes execution order.

## UML component view

A UML component diagram describes modular structure and dependencies, including interface contracts. It is a separate view, not an extra C4 level. Use an explicit mapping when a UML component corresponds to a C4 container or component; there is no universal one-to-one correspondence. The [UML 2.5.1 specification](https://www.omg.org/spec/UML/2.5.1/PDF) is the normative reference (components §11.6, ports §11.3, interfaces §10.4).

| Construct | Meaning and drawing |
| --- | --- |
| Component | `uml-component` node: rectangle with `«component»` and the component icon. |
| Provided interface | `provides: ["IName"]`: a named circle (lollipop) on the provider. |
| Required interface | `requires: ["IName"]`: a named half circle (socket) on the consumer. |
| Dependency / usage | `dependency` edge: dashed, open arrowhead from client to supplier; label `«use»` or the need. |
| Interface realization | `realization` edge: dashed, hollow triangle toward a `uml-interface` node. |
| Assembly connector | `assembly` edge from the consumer to the provider, labelled with the interface; drawn as ball-and-socket. It is not a request direction. |
| Delegation connector | `delegation` edge from an enclosing component to the inner part that does the work, when that structure is known. |

Show interfaces only when supported by the architecture input or explicitly proposed design. If only coarse dependencies are known, a UML component dependency view is valid; label its scope and omit invented contracts. A REST endpoint may participate in a contract, but an endpoint list does not automatically establish UML interfaces.

## Small modeling example

For supplied facts “a shopper uses a browser shop; it calls an order API backed by a database; the API contains checkout and payment adapter modules”:

- L1: Shopper, Shop system, and any stated external systems.
- L2: Browser shop, Order API, and Database inside Shop.
- L3, scoped to Order API: Checkout and Payment adapter, with only stated dependencies.
- L4: Missing until specific code elements or a proposed implementation are supplied.
- UML: Components and known dependencies; add payment contracts only if specified.

This is an abstraction example, not a default architecture to insert into other projects. It is built out in full in `<root>/shared/examples/c4.data.js`.

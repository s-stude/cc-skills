# Dependency semantics and research

Use these distinctions to choose what to draw and what conclusions the evidence permits. The guidance synthesizes the primary sources linked below; it does not require their tools or impose their architecture on the user's project. Sources checked on 2026-11-01.

## Graph, structure, and relationships

| Concept | Meaning in the learning page | Modeling consequence |
| --- | --- | --- |
| Module | A named unit of organization or encapsulation at the chosen level | State the granularity; keep files, packages, and services distinguishable |
| Module dependency graph | Directed graph of modules and “depends on” relationships | It is neither necessarily a tree nor necessarily acyclic |
| Internal structure | Parts within a module, their roles, public surface, and relationships | Containment describes membership; dependency describes need |
| Dependency | Another unit, contract, resource, or artifact needed in a stated context | Label the kind and reason; separate compile/build/runtime conditions |
| Dependent | A unit that depends on the selected unit | Read incoming edges under the page's arrow convention |

The [Nx project graph documentation](https://nx.dev/docs/features/explore-graph) illustrates deriving relationships from source, configuration, and installed dependencies, tracing paths, and opening the files behind an edge. Apply its evidence and drill-down ideas without assuming that all projects use Nx or that a source scan captures every runtime relationship.

The [C4 component view](https://c4model.com/diagrams/component) describes a container's internal components and responsibilities. The [C4 code view](https://c4model.com/diagrams/code) goes inside a component to selected implementation elements. Borrow this progressive zoom for module internals; do not equate every module with a C4 component or force a full C4 hierarchy. A folder tree supplies containment clues, not proof of responsibilities or dependencies.

## Direction and reachability

With `A → B`, A consumes or needs B. B is a dependency of A; A is a dependent of B. Direct dependencies are outgoing neighbors. Direct dependents are incoming neighbors.

For `A → B → C`, C is reachable transitively from A. That path does not prove a direct A-to-C dependency. A direct edge can coexist with an indirect path. “Transitive dependencies” sometimes includes direct ones; in the UI use “all reachable dependencies” or “indirect only” to state which set is shown. Exclude the starting node from its own dependency list and report a returning path as a cycle.

The [Bazel dependency concepts](https://bazel.build/concepts/dependencies) distinguish declared from actual dependencies and define direct versus transitive reachability. Bazel build targets form a DAG; general source/module graphs may contain cycles. Do not export the build tool's acyclicity assumption to other relationship types.

## Keep evidence and dependency kinds distinct

| Evidence | Supports | Does not establish by itself |
| --- | --- | --- |
| Manifest or build declaration | A declared package/target relationship in its scope | Actual use by every contained module |
| Resolved source import or reference | A source relationship to a module/symbol | Execution on every request, or even runtime presence for type-only imports |
| Lockfile | Resolved package versions and installation relationships | Module-level use or a complete runtime call graph |
| DI registration/configuration | Configured provider/consumer binding under stated conditions | That every deployment uses that binding |
| Observed runtime trace | Relationships exercised in that trace | Exhaustive behavior across all paths/environments |
| Documentation or user prose | Described design or intended relationship | Confirmation that code implements it |

Use specific relationship labels such as “imports,” “uses type,” “links,” “loads dynamically,” “calls API,” or “test fixture.” Keep external packages and runtime resources distinguishable from internal modules. Do not infer a dependency solely from similarly named folders. For a runtime call through an interface, show the contract and configured provider only as far as the evidence supports.

Dependency arrows are not a timeline or a data-flow diagram. A depends on B even when B returns data to A. Event producers and consumers may each depend on a broker or shared schema without importing each other. Explain the evidenced contract rather than inventing a direct source edge.

## Cycles, layers, and impact

- A cycle returns to its starting node along directed edges. Strongly connected components identify mutually reachable groups; a multi-node component, or a single node with a self-loop, indicates a cycle. Show a representative cycle path rather than enumerating every possible cycle. See [NetworkX strongly connected components](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.strongly_connected_components.html).
- Topological ordering exists only for an acyclic graph. With consumer-to-dependency arrows, the usual topological ordering puts consumers first; reverse it for dependency-first study/build order. Collapsing cyclic components gives an ordering of groups, not a valid order within each group. See [NetworkX topological sort](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.topological_sort.html).
- Reverse reachability gives candidates for change impact. It does not prove all dependents break: public contracts, compatibility, conditions, and tests matter. Explain a concrete potential propagation path with this limitation.
- Incoming/outgoing neighbor counts can indicate reuse or breadth of dependency. State whether counts refer to distinct modules or individual relationships and which filters apply. They do not measure internal cohesion or prove architectural quality.
- Label a dependency a layer violation only against an evidenced architecture rule. A cycle can be significant without being universally illegal; its consequences depend on language, loading, build rules, and runtime behavior.

## Small reasoning check

For illustrative edges `UI → Orders`, `Orders → Storage`, `Worker → Orders`, and `Storage → Orders`:

- UI directly depends on Orders and indirectly reaches Storage.
- Orders has direct dependents UI, Worker, and Storage.
- Orders and Storage form a cyclic group. There is no dependency-first ordering of the individual modules that satisfies all edges.
- A Storage contract change potentially affects Orders and, through it, UI and Worker. This is a review scope, not a prediction of certain failures.

This is an illustrative fixture only. Do not insert these modules into the user's graph without evidence.

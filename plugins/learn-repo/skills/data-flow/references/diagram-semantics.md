# Diagram semantics and research

Use these rules when translating context into diagrams. These are complementary views, not interchangeable names for a generic flowchart. Sources were consulted on 2026-11-01; the teaching conventions below combine those sources with practical presentation guidance.

## Data flow diagram (DFD)

A DFD models information movement and transformation within a declared boundary. Its four elements are external entities, processes, data stores, and directed data flows. External means outside the chosen boundary, not necessarily outside the organization.

The template draws Gane–Sarson notation: rounded process boxes, open-ended data-store rectangles, plain rectangles for external entities. Say so in the view's `read` text when the audience may know Yourdon notation (circles and parallel lines) instead.

Use verb phrases for processes and nouns for entities, stores, and data carried by arrows. Draw separate directed arrows for reads and writes with distinct payload labels. In a conventional DFD, entity-to-store, store-to-store, or entity-to-entity transfer requires an intervening process inside the modeled system. If that process is not evidenced, expose the missing detail rather than inventing it. Every modeled process needs meaningful input and output; outputs must be explainable by inputs and accessible stored data.

A context view treats the system as one process and displays external exchanges, without internal stores. Decomposition exposes internal processes and stores. Preserve the parent's boundary inputs and outputs across decomposition (“balancing”); a parent flow can split into named constituent flows if their equivalence is explained. Level numbering differs across sources, so label views “Context” and “Decomposition” and declare any numeric convention.

A logical DFD explains business functions; a physical DFD adds implementation specifics. Declare which perspective is used. Neither arrow placement nor process numbers establishes timing. Decisions, retries, schedules, and execution sequence belong in a separate operational explanation, not control arrows disguised as DFD data flows.

Sources: [IBM: DFD components, notation, perspectives, and rules](https://www.ibm.com/think/topics/data-flow-diagram); [Kenneth A. Kozar, University of Colorado: DFDs, boundaries, leveling, and absence of control/timing](https://spot.colorado.edu/~kozar/DFD.html).

## Data lineage graph

Lineage explains origin and derivation: which inputs contribute to an output, through which transformation, and which downstream assets depend on a source. A useful representation alternates dataset → job/transformation → dataset; a simpler dataset-to-dataset graph can label edges with the transformation. Declare the chosen representation.

Distinguish a reusable job definition from a particular run. Static SQL or code can establish designed dependencies; runtime events can establish observed dependencies for a specific run. Do not invent timestamps, freshness, row counts, or execution success from source code alone. Dataset identity should include enough namespace information to distinguish similarly named tables in different systems.

Dataset-level evidence does not prove column-level mappings. Show field lineage only where expressions or metadata establish it. Distinguish fields used to compute a value from fields used in filters, joins, or grouping: both can affect the result, but in different ways. Show the expression and role rather than implying every influence is a copied value. A foreign-key relationship by itself is not evidence of data derivation.

“Upstream” traverses toward source dependencies; “downstream” traverses toward consumers. Keep traversals safe for cycles. Do not silently discard feedback loops to make a DAG; use dataset versions/time boundaries where evidenced, or annotate the cycle. Lineage is not a schedule or proof of execution order.

Sources: [OpenLineage object model: datasets, jobs, runs, and static/runtime lineage](https://openlineage.io/docs/spec/object-model/); [OpenLineage column lineage: field dependencies and transformation information](https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/).

## ETL/ELT pipeline diagram

ETL means extract data from sources, transform it, then load it into the target. ELT loads extracted data into the target before transforming it there. State the target boundary: intermediate staging writes do not alone determine whether the overall pipeline is ETL or ELT. Preserve a hybrid sequence when that is what the evidence shows.

There is no single required symbol set for an ETL diagram. Make datasets, processing stages, and orchestration distinguishable. Show actual intermediate artifacts and concrete operations: for example, parsing, validating, deduplicating, joining, or aggregating. Label data edges with what moves. If execution prerequisites also appear, use a separate labeled edge style; a scheduler dependency does not necessarily carry data.

Add batch/streaming mode, triggers, full/incremental loading, checkpoints, validation failures, quarantine outputs, retry behavior, or load semantics only when supported and useful to the learning goal. Mark unknowns instead of selecting a plausible implementation. A source-to-dashboard pipeline may branch and rejoin; it need not be a single three-box chain. An ordinary application read/write path is not automatically an ETL pipeline.

Source: [AWS: extraction, transformation, loading, and ETL versus ELT](https://aws.amazon.com/what-is/etl/).

## Example of complementary views

The following is fictional teaching material, not a default architecture to impose on user context. It is built out in full in `<root>/shared/examples/data-flow.data.js`.

Suppose an order system sends line items to an analytics service. A daily job validates quantity and unit price, calculates line amounts, aggregates by day, and loads a daily sales table read by a dashboard.

- **DFD:** With the analytics service as the boundary, show the order system sending “order line records,” processes “Validate lines” and “Calculate daily sales,” a “Daily sales” store, and a dashboard receiving “daily totals.” Show the transformation processes between entities and stores. If the example includes rejected lines, state their destination and preserve that output in the context view.
- **Lineage:** Show `order_lines` → calculation/aggregation job → `daily_sales` → dashboard. At field level, `quantity` and `unit_price` contribute to `SUM(quantity * unit_price)`; the day field determines grouping. Explain which records are excluded by validation.
- **Pipeline:** Show extraction → validation → amount calculation → daily aggregation → target load. Label it ETL because transformation precedes loading into the stated target. If raw lines were loaded into that target first and transformed there, the view would instead show ELT.

An illustrative line with quantity 2 and unit price 15 contributes 30 to its day's total. It is a contribution to an aggregate, not the entire total unless it is the only accepted line. That distinction should remain consistent in every diagram and walkthrough.

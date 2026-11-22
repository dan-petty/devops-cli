## Purpose
What `devops ai rag status` shows for each Qdrant collection of the RAG store, and the point of the collection that gives each value of its row.

## ADDED Requirements

### Requirement: Last Indexed shows the newest point of the collection
The "Last Indexed" column of `devops ai rag status` SHALL show the `indexed_at` value of the point of the collection with the newest `indexed_at`, from a scroll of one point that Qdrant orders by `indexed_at` with the newest first. When Qdrant refuses that scroll, the column SHALL show `—`, and the other columns of the row SHALL still show their values. Status SHALL NOT write to the store.

#### Scenario: An old first point and a newer later point
- **WHEN** `devops ai rag status` runs, and the first point of the collection `devops_docs` holds `indexed_at` `2026-11-22T04:43:12.093718+00:00` and a later point holds `2026-11-22T14:31:05.512000+00:00`
- **THEN** the row of `devops_docs` shows `2026-11-22 14:31:05` in "Last Indexed", and the output does not hold `04:43:12`

#### Scenario: Qdrant refuses the order
- **WHEN** `devops ai rag status` runs, and the store refuses the scroll that orders by `indexed_at` with `QdrantClientError`, as a collection with no datetime index does
- **THEN** the command exits 0, "Last Indexed" shows `—`, and the row still shows the embedding model and the KB digest of the collection

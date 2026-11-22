## ADDED Requirements

### Requirement: Each collection holds a datetime index of indexed_at
`QdrantClient.ensure_collection` SHALL create a payload index for each entry of `CONST_RAG_PAYLOAD_INDEXES` that the payload schema of the collection does not hold, with the schema type of the entry: a tenant `keyword` index on `project_name`, a `keyword` index on `file_path` and on `visibility`, and a `datetime` index on `indexed_at`. It SHALL do this for a new collection and for a collection that exists.

#### Scenario: A new collection
- **WHEN** `ensure_collection("docs", 4)` runs on a store that does not hold `docs`
- **THEN** the client asks for the indexes `project_name` (keyword, tenant), `file_path` (keyword), `visibility` (keyword) and `indexed_at` (datetime), in that order

#### Scenario: A collection with no payload index
- **WHEN** `ensure_collection("docs", 4)` runs on a store whose collection `docs` holds no payload index
- **THEN** the client asks for the same four indexes and does not create the collection again

# Design

## Decisions

- The job uses the tiers of `EmbeddingsEngine`: memory, Valkey, then the disk tier under the data directory. The engine keys a vector by the provider, the model name that the request sends and the SHA-256 of the text, so a changed text or another model is a miss, as the removed file was.
- The job keeps the text that it embeds: the title and the text of a person (`text_of_a_person`). A section that the refine job or the alternatives job writes does not change the text, so it gives a cache hit.
- `embed_issues` sends each distinct text once in one call, as the removed file did by its hash. Two items with the same title and body get the same vector.
- The test of the second run goes through the command: two runs, each with a new engine, the HTTP fake in place of the gateway and the configured Valkey refusing each connection. The second run sends no request, and the lookup counter shows disk hits only.

## Rejected alternatives

- Keep `embeddings.json` and also give the engine the disk tier: two stores for the same vectors, which the owner rule forbids.
- Move the file into Valkey only: a workstation has no Valkey at the default `valkey.url`, so each run would embed every open item again. The disk tier covers that case, and the Valkey key fix is #4569.
- Keep `Edges.embedding_model` for the plan file: the plan records no model name, and no code reads the field after the file is removed.

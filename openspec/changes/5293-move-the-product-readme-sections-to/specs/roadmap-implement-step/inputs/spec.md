## MODIFIED Requirements

### Requirement: The routes name the documents of a group
The step SHALL add the named sections of a routed document to the message when a path that the group names in a code span matches a route. Each document has its own heading and is cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. Each route SHALL name a row of the "Where to look" table of `AGENTS.md` that links its document.

#### Scenario: A group that changes a test
- **WHEN** a group names `tests/test_sample.py`
- **THEN** the message holds the section "Doubles" of `docs/TESTING.md`

#### Scenario: A group that changes only a manifest
- **WHEN** a group names only `k8s/sample.yaml`
- **THEN** the message holds a section of `k8s/README.md` and the section "Image Pins" of `docs/CLUSTER.md`, and holds nothing of `docs/TESTING.md`

#### Scenario: A route drifts from AGENTS.md
- **WHEN** a route names a "When you" cell that the table lacks, or a document that the row does not link
- **THEN** the test of the routes fails and names the route

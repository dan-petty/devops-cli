## MODIFIED Requirements

### Requirement: The inputs of a step are fixed
The user message of the model SHALL hold the text of the `AGENTS.md` of the checkout under the heading "Rules of the repository (AGENTS.md)", the title, problem statement and acceptance criteria of the item, the `proposal.md`, `design.md` and `tasks.md` of the change, the group, the files that the group names, packed, the routed sections of the documents (see "The routes name the documents of a group"), and, except for a fix step, the path of the `tasks.md` under the heading "The tasks file". It SHALL hold nothing else. A checkout with no `AGENTS.md` gets no such section. The change is the one folder `openspec/changes/<N>-*/` of the checkout, and the step SHALL raise `RoadmapImplementError` when there is none or more than one.

#### Scenario: The first request
- **WHEN** the step runs group 1 of a change whose group 1 names `src/sample.py` and `tests/test_sample.py`, which does not exist yet
- **THEN** the first request holds the item title, the two sections of the issue, the three documents, the text of group 1, the packed `src/sample.py`, the path `openspec/changes/1-sample-change/tasks.md` and the text of `AGENTS.md`, and it holds no text of another file

#### Scenario: A fix step
- **WHEN** a fix step builds its inputs
- **THEN** the message holds no section "The tasks file", and it holds `AGENTS.md`

#### Scenario: A missing change
- **WHEN** the checkout holds no folder `openspec/changes/7-*/`
- **THEN** the step raises `RoadmapImplementError` that names the pattern

## ADDED Requirements

### Requirement: The routes name the documents of a group
The step SHALL add the named sections of a routed document to the message when a path that the group names in a code span matches a route. Each document has its own heading and is cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. Each route SHALL name a row of the "Where to look" table of `AGENTS.md` that links its document.

#### Scenario: A group that changes a test
- **WHEN** a group names `tests/test_sample.py`
- **THEN** the message holds the section "Doubles" of `docs/TESTING.md`

#### Scenario: A group that changes only a manifest
- **WHEN** a group names only `k8s/sample.yaml`
- **THEN** the message holds a section of `k8s/README.md` and holds nothing of `docs/TESTING.md`

#### Scenario: A route drifts from AGENTS.md
- **WHEN** a route names a "When you" cell that the table lacks, or a document that the row does not link
- **THEN** the test of the routes fails and names the route

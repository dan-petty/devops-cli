# Tasks

## 1. Share the nearest-item function

Kind: behavior. Reads: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/ai/vector_similarity.py`. Changes: `src/devops_cli/roadmap/nearest.py`, `src/devops_cli/roadmap/intake.py`, `tests/roadmap/test_roadmap_nearest.py`.

- [x] 1.1 Write tests for `nearest` and `embedding_text`: the closest first, equal scores in input order, a limit above the count, the text cut at the limit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_nearest.py` fails on the base
- [x] 1.2 Add `nearest` and `embedding_text`, and call them from the intake planner and from `Subject.text` and `_Entry.text`. Delete the inline ranking
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_nearest.py tests/roadmap/test_roadmap_intake.py` passes

## 2. Read blocked-by links

Kind: behavior. Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `tests/roadmap_github_fake.py`, `tests/roadmap/test_roadmap_store_contract.py`.

- [x] 2.1 Write contract tests for both stores: the blockers of an issue, the count in the issue listing, an issue with no blocker, a blocker of another repository, a number that is no issue
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py` fails on the base
- [x] 2.2 Add `IssueRecord.blocked_by`, `RoadmapStore.blocked_by`, the GitHub read of `dependencies/blocked_by`, the in-memory read and `seed_blocked_by`, and the fake route
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py` passes

## 3. Build the shortlists and the groups

Kind: behavior. Reads: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/body_hash.py`. Changes: `src/devops_cli/roadmap/consolidate_shortlist.py`, `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_consolidate_shortlist.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 3.1 Write tests for the citation, link and embedding signals, the cap on common citations, the cap on members, the contest rule, the pair rule, the order of the input, the cache of embeddings (second run, edit, section of a job, another model, pruning, a file that cannot be read) and the read of a store
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_consolidate_shortlist.py` fails on the base
- [x] 3.2 Add `consolidate_shortlist.py`, `text_of_a_person` in `body_hash.py`, the two defaults and the two constants, and the entries of the new defaults in the table of limits
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_consolidate_shortlist.py tests/roadmap/test_roadmap_limit_classes.py` passes

## Criteria

- Group 1: A test: `nearest` returns the closest keys first and keeps the input order for equal scores. The tests of intake do not change.
- Group 2: A test, on the in-memory store and on the GitHub store over its fake: `blocked_by(3)` returns `[1]` and the listing counts 1.
- Group 3: A test: two bodies that cite the same path and identifier give the evidence "shared path and identifier".
- Group 3: A test: a second run over the same issues makes no call to the embedder.
- Group 3: A test: an item that two anchors want joins the anchor with the stronger evidence, and on a tie the lower number.

## Workflow follow-up

- #3740 builds the command, the plan file and the model steps on these shortlists.
- #3743 applies one group.
- #3745 adds the MCP mirror and the weekly row.
- #3635 checks the dry run on the live board.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

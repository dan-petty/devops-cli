# Tasks

## 1. Show the reason, the tools and the result counts in the comment

kind: behavior

Reads: `src/devops_cli/roadmap/alternatives.py` (`AlternativesTools`, `Check`, `_comment_of`, `validate_reply`), `src/devops_cli/lang/en/messages.py` (the `alternatives_comment_*` strings), `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: the same files, and `src/devops_cli/config/constants.py`.

- [x] 1.1 Write the failing tests first: the result count of a search, the comment with the reason and the counts, the list of tools considered, the schema refusal of a reply with no reason, the bound of sources, and the unchanged first comment. Update the expected comment of `test_a_covering_tool_makes_one_comment_one_block_and_the_record`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`
- [x] 1.2 Add `reason` to `AlternativesReply`, `Search` and `AlternativesTools.searches`, the `reason`, `considered` and `searches` fields of `Check`, the three comment sections and the bound `CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES`, and ask for `reason` in the prompt.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_trust.py`

## 2. Documents and checks

kind: documents

- [x] 2.1 Fix the module docstring of `alternatives.py` and the spec delta, then check the change.
  - Verification: `uv run devops openspec check`
- [x] 2.2 Run the full CI.
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

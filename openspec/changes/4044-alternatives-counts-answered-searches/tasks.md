# Tasks

## 1. Only an answered search counts in the alternatives check

Kind: behavior.

Reads: `src/devops_cli/ai/web_search.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/alternatives.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`. Creates: `tests/roadmap/test_roadmap_alternatives_search.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_alternatives_search.py`, write the cases `shared_text`, `empty_answer` and `all_searches_failed`, and the refused query, a later answered search and the limit of failed searches
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_search.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/refine/refine_investigation.py`, make `cited_web_search` return a frozen result with `text` and `answered`, and use `.text` in the refine tool. Change the three tests of `cited_web_search` in `tests/roadmap/refine/test_roadmap_refine_investigation.py` to read the result
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`
- [ ] 1.3 In `src/devops_cli/roadmap/alternatives.py`, record a `Search` only for an answered search, count every call in a separate attempt counter for the limit, and fix the docstring of `Search`. In `src/devops_cli/lang/en/messages.py` and `src/devops_cli/ai/tasks/roadmap_alternatives.md`, say "answered search"
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_search.py` passes
- [ ] 1.4 Keep the other alternatives tests green
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`

## 2. The documents say answered search

Kind: documents.

Changes: `docs/roadmap/alternatives.md`, `docs/TELEMETRY.md`.

- [ ] 2.1 In `docs/roadmap/alternatives.md`, say that the check accepts a verdict only after an answered search and that the comment lists the answered searches. In `docs/TELEMETRY.md`, say that the histogram counts answered searches and that a search that no provider answered does not count
  - Verification: `$ uv run devops ci docs`
- [ ] 2.2 No text of the change keeps the old rule
  - Verification: `$ ! git grep -n "A search that a provider refused counts" docs/ src/`

## Criteria

- Group 1: `cited_web_search` SHALL return the text of the answer and the flag `answered`, and the refine tool SHALL keep its text.
- Group 1: The alternatives tools SHALL record a search only when a provider answered it.
- Group 1: A reply that follows no answered search SHALL end as a failed check.
- Group 1: Every call of `search_web` SHALL count toward the search limit.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

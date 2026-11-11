# Tasks

## 1. Show each read tool answer format whole
kind: behavior

- [x] 1.1 Add a test that builds the tools of `StageTools(toolset="research")` and of `InvestigationTools(web=True)` and asserts that the description of `search_code`, `callers`, `file_symbols` and `find_issues` holds its answer format whole, and that no description has a `<returns>` part. It fails on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py`
- [x] 1.2 Move the answer format of `callers` and `file_symbols` in `src/devops_cli/roadmap/stage/stage_tools.py`, and of `search_code` in `src/devops_cli/roadmap/refine/refine_investigation.py`, into the summary of the docstring, and remove the `Returns:` sections.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py tests/roadmap/refine/test_roadmap_refine_investigation.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

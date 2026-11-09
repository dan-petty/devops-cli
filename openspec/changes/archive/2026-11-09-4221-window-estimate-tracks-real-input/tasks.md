# Tasks

## 1. Make the window estimate follow the reported input

Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_investigation_window.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`.

- [x] 1.1 Write the tests of the estimate, the limit, the first request and a reply that reports no input, and the guard test of the retry text, and watch the four tests of the estimate fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation_window.py`
- [x] 1.2 Change `tokens_of` to take the last reply's `input_tokens` and `output_tokens` plus the count of the text after it, and to count the text parts when no reply reports an input. Fix the numbers of the tests that name the size of a first request, at the cause, without a looser threshold
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation_window.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`

## Workflow follow-up

- Criterion 3 of the issue is dropped: the unknown tool name does not use the output retry (see the proposal). The edit of the issue body states this.
- Pending a person: run `devops roadmap stage --plan --item 3599` with the Service config and check that each request whose real input is under 150,000 tokens offers its tools (criterion 5 of the issue).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

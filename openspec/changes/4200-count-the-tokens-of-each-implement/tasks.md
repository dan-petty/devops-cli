# Tasks

## 1. Count the tokens of each Job once

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stores/store.py`. Changes: the same files, and the tests below.

- [x] 1.1 Add the failing tests: `test_two_jobs_of_one_item_count_each_token_once`, `test_a_spend_below_the_counted_spend_is_counted_whole_and_becomes_the_counted_spend`, `test_a_record_of_an_older_version_counts_its_whole_spend_once` and `test_a_report_without_new_spend_counts_no_tokens` in `tests/roadmap/implement/test_roadmap_implement_submit.py`; the retry and return tests in `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`; the old-record load test in `tests/roadmap/implement/test_roadmap_implement_records.py`; and the reader line in `tests/invariants/test_roadmap_implement_record_keys.py`. They fail on the base
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Add `SPEND_COUNTED = "implement.spend_counted"` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`, and add it to the docstring of the class
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_records.py`
- [ ] 1.3 In `src/devops_cli/roadmap/implement/implement_submit.py`, read the spend and the counted total once in `_report`, write the new total with `implement.job_state`, and pass only the delta to `_emit_implement_metrics`, which no longer reads the spend itself
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/invariants/test_roadmap_implement_record_keys.py`
- [ ] 1.4 In `src/devops_cli/roadmap/implement/implement_run.py`, clear `implement.spend_counted` with `implement.spend` at the retry start and at the return to New
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phase_marks.py`

## 2. Document the record key

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 2.1 Add `implement.spend_counted` to the record table of `docs/ROADMAP_WORKFLOW.md`: the token total that the Service has added to the token counter, which a retry and a return to New clear with `implement.spend`
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_implement_record_keys.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

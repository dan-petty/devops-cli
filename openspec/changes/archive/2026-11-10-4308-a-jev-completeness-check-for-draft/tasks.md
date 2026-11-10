# Tasks

## 1. The check

- [x] 1.1 Add tests for the Jev completeness check: the shape of the request, a doubt, a weak test score, an error, a skip, and the counter
  - Verification: `$ uv run devops ci test tests/roadmap/test_jev_completeness.py`
- [x] 1.2 Add `src/devops_cli/roadmap/jev_completeness.py`, the constants, the messages and the instrument `ROADMAP_JEV_COMPLETENESS_TOTAL`
  - Verification: `$ uv run devops ci test tests/roadmap/test_jev_completeness.py`

## 2. The row stage_ready

- [x] 2.1 Add tests for the row: setting off, a pass, a doubt with one note, a new head commit, an error, and a failed check
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_ready_jev.py`
- [x] 2.2 Add the setting `roadmap.stage.jev_completeness`, the record key `stage.jev` and the call in `stage_ready.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_ready_jev.py tests/roadmap/stage/test_roadmap_stage_ready.py`

## 3. The labelled set and the eval

- [x] 3.1 Add tests for the set, the rates, the decision on the switch and the command
  - Verification: `$ uv run devops ci test tests/roadmap/test_jev_completeness_eval.py`
- [x] 3.2 Add the 47 cases, `jev_completeness_eval.py` and `devops roadmap eval completeness`
  - Verification: `$ uv run devops ci test tests/roadmap/test_jev_completeness_eval.py`

## 4. Documents

- [x] 4.1 Describe `stage.jev` in `docs/ROADMAP_WORKFLOW.md` and regenerate the configuration, variable, metric and command documents
  - Verification: `$ uv run devops ci docs`

# Tasks

## 1. Tests (RED)
- [x] Add tests in `tests/roadmap/test_roadmap_alternatives_reply_fixable.py` verifying `job_verdict`, `no_search`, and `skip_only` with matching `earlier_code` get one return with `band=continue` in `shadow`, one return in `off`, and zero returns in `on`.

## 2. Implementation (GREEN)
- [x] Update `_OutputChecker.check` in `src/devops_cli/roadmap/alternatives.py` so `Band.CONTINUE` stops returns only in `Mode.ON`.

## 3. Verification
- [x] Run pytest on `tests/roadmap/test_roadmap_alternatives_reply_fixable.py` and `tests/roadmap/test_roadmap_alternatives*.py`.
- [x] Run `devops ci fail-to-pass --base origin/main`, `ruff`, `mypy`, `devops openspec check`, and static CI gates.

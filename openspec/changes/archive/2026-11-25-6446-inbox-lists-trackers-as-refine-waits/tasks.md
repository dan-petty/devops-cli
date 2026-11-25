# Tasks

## 1. Tests (RED)
- [x] Add tests in `tests/roadmap/test_roadmap_inbox.py` verifying tracker items (`type/epic` and `sub_issues > 0`) produce no `refine`, `split`, `alternatives`, `failed`, or `owner` lines while non-trackers do.
- [x] Add test in `tests/roadmap/test_roadmap_inbox_gauges.py` verifying trackers with refine waits do not increment `devops_cli_roadmap_inbox_items`.
- [x] Add tests in `tests/roadmap/test_roadmap_phase.py` verifying `has_person_cause` returns `False` for refine/owner keys on trackers and `True` on non-trackers.

## 2. Implementation (GREEN)
- [x] Update `refine_wait_on_person`, `_split_lines`, `_alternatives_lines`, `_failed_lines`, and `_owner_lines` in `src/devops_cli/roadmap/inbox.py` to skip `item.is_tracker`.
- [x] Update `has_person_cause` in `src/devops_cli/roadmap/phase.py` to ignore refine and owner-question keys when `item.is_tracker` is true.
- [x] Update `docs/roadmap/inbox.md` to state that trackers are excluded from refine waits and owner questions.

## 3. Verification
- [x] Run pytest on `test_roadmap_inbox.py`, `test_roadmap_inbox_gauges.py`, and `test_roadmap_phase.py`.
- [x] Run `devops ci fail-to-pass --base origin/main`, `devops openspec check`, `ruff`, `mypy`, and static CI gates.

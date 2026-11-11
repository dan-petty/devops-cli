# Tasks

## 1. Behavior

- [x] 1.1 Add tests: a mark with a probability above 1 or below 0 counts as unreadable and the other marks are read, a probability of 1.0 is in the last band, and a Jev answer out of range counts `jev_error` and records no mark
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`
- [x] 1.2 Bound `ShadowAnswer.probability` to 0 to 1 and catch `ValidationError` in `ShadowIntakeModel.observation`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`

## 2. Documents

- [x] 2.1 Say in `docs/roadmap/intake.md` that a mark with a probability out of range is unreadable
  - Verification: `$ uv run devops ci docs`

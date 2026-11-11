# Tasks

## 1. Behavior

- [x] 1.1 Add tests: a mark with a probability above 1 or below 0 counts as unreadable and the other marks are read, a probability of 1.0 is in the last band
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py`
- [x] 1.2 Bound `ShadowAnswer.probability` to 0 to 1
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_jev_shadow_report.py`

## 2. Documents

- [x] 2.1 Say in `docs/roadmap/intake.md` that a mark with a probability out of range is unreadable
  - Verification: `$ uv run devops ci docs`

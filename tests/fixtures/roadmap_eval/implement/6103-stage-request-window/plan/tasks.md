# Tasks

## 1. Behavior

- [ ] 1.1 Ask the window test for 512 tokens of room below the limit for code at the caps; it fails at 2b4ae1f67
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py`
- [ ] 1.2 Lower `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` to 19,456 tokens and correct its comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py`

## 2. Documents

- [ ] 2.1 Give the new cap in `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs`

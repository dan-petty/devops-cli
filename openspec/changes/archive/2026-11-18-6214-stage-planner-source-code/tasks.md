# Tasks

## 1. Prompts

- [x] 1.1 State the source-code rule in `roadmap_stage_change.md` and `roadmap_stage_split.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 1.2 Run the live stage eval at the base and the head and put both scores in the pull request body
  - Verification: `$ uv run devops roadmap eval stage --limit 3`

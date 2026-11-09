# Tasks

## 1. Read a quoted tuple only where the plan names the exposure table

Reads: `src/devops_cli/roadmap/stage/stage_commands.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`. Changes: `src/devops_cli/roadmap/stage/stage_commands.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`.

- [x] 1.1 Add failing tests: a tuple of another table is no key; the sentence decides; the constant name gives the context; a task text with the context is checked
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py`
- [x] 1.2 Check a quoted tuple in `_mcp_exposure_problems` only when `_sentence_around` holds the exposure table context
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py`

## 2. Check the golden set and the specs

- [x] 2.1 Replay the golden set of the stage eval through the gates
  - Verification: `$ uv run devops roadmap eval stage --replay`
- [x] 2.2 Validate the specs
  - Verification: `$ uv run devops openspec check`

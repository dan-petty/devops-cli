# Tasks

## 1. Failing tests

- [x] Add assertion in `tests/test_instruction_generator.py` and unit test in `tests/test_agents_md_claims.py`
  - Verification: `uv run pytest tests/test_instruction_generator.py tests/test_agents_md_claims.py`

## 2. Agent instructions and template

- [x] Update Rule 2 in `AGENTS.md` and trim prose to preserve the character budget
  - Verification: `uv run pytest tests/test_agents_md_claims.py -k test_agents_md_stays_within_character_budget`
- [x] Update Rule 2 in `src/devops_cli/templates/AGENTS.md.j2`
  - Verification: `uv run pytest tests/test_instruction_generator.py`

## 3. Verification and static checks

- [x] Verify openspec check and docs check
  - Verification: `uv run devops openspec check && uv run devops docs check`
- [x] Run static checks
  - Verification: `uv run ruff check && uv run ruff format --check`

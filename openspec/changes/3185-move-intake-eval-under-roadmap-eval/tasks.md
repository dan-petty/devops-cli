# Tasks

## 1. Move the intake evaluation into the eval group

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `tests/roadmap/test_roadmap_duplicate_eval.py`, `tests/roadmap/test_roadmap_intake.py`, `tests/ai/mcp/test_mcp.py`, `tests/fixtures/dry_run_gaps.json`. Changes: `src/devops_cli/commands/roadmap_eval_intake.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `tests/commands/test_roadmap_eval_intake.py` (new), `tests/roadmap/test_roadmap_duplicate_eval.py`, `tests/roadmap/test_roadmap_intake.py`, `tests/ai/mcp/test_mcp.py`, `tests/fixtures/dry_run_gaps.json`.

- [ ] 1.1 Add a failing test that `devops roadmap eval intake --help` exits 0 and `devops roadmap intake-eval` exits 2, and verify that `uv run devops ci test tests/commands/test_roadmap_eval_intake.py` fails on the base
- [ ] 1.2 Move `intake-eval` to `roadmap_eval_intake.py` on `eval_app`, delete gap entry from `dry_run_gaps.json`, update `test_mcp.py`, `test_roadmap_duplicate_eval.py`, and `test_roadmap_intake.py`, and verify that `uv run devops ci test tests/commands/test_roadmap_eval_intake.py` passes

## 2. Update handbook documentation and case data references

Reads: `docs/roadmap/intake.md`, `src/devops_cli/roadmap/intake_duplicate_cases.json`. Changes: `docs/roadmap/intake.md`, `src/devops_cli/roadmap/intake_duplicate_cases.json`.

- [ ] 2.1 Update command references in `docs/roadmap/intake.md` and `src/devops_cli/roadmap/intake_duplicate_cases.json`, and verify that `! git grep -n "intake-eval" docs/roadmap/intake.md src/devops_cli/roadmap/intake_duplicate_cases.json` passes

## 3. Regenerate command reference documentation and verify clean tree

Reads: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `src/devops_cli/commands/roadmap_eval_intake.py`. Changes: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [ ] 3.1 Update CLI reference documentation in `README.md`, `docs/CLI_REFERENCE.md`, and `docs/commands/roadmap.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
- [ ] 3.2 Verify that no live repository file names `intake-eval` outside the changelog and change archives, and verify that `! git grep -n "intake-eval" -- ':!CHANGELOG.md' ':!openspec/changes/'` passes

## Criteria

- The CLI SHALL run the intake duplicate evaluation as `devops roadmap eval intake`.: group 1
- The CLI MUST NOT keep `devops roadmap intake-eval` as a command or as an alias.: group 1
- The moved command SHALL keep its `--dry-run` option and its scoring output.: group 1
- The command SHALL live in `src/devops_cli/commands/roadmap_eval_intake.py` and MUST be registered on `eval_app`.: group 1
- The MCP exclusion list MUST hold `("roadmap", "eval", "intake")` and no `("roadmap", "intake-eval")` entry.: group 1
- No live file SHALL name `intake-eval` after the change.: group 3
- The command matrix and the CLI reference SHALL list `devops roadmap eval intake` and MUST NOT list `devops roadmap intake-eval`.: group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

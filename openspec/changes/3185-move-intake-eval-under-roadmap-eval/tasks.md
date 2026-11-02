# Tasks

## 1. Move the intake evaluation into the eval group

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/commands/roadmap_eval_implement.py`, `tests/commands/test_roadmap_eval_implement.py`, `tests/roadmap/test_roadmap_duplicate_eval.py`. Changes: `src/devops_cli/commands/roadmap_eval_intake.py` (new), `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `tests/commands/test_roadmap_eval_intake.py` (new).

- [ ] 1.1 Write `tests/commands/test_roadmap_eval_intake.py`: it asserts that `devops roadmap eval intake --help` exits 0 and names the intake duplicate evaluation, that the names of `eval_app` include `intake`, and that `devops roadmap intake-eval` exits 2 with no such command, and verify that `uv run devops ci test tests/commands/test_roadmap_eval_intake.py` fails on the base
- [ ] 1.2 Move the `intake-eval` command function out of `src/devops_cli/commands/roadmap.py` into the new `src/devops_cli/commands/roadmap_eval_intake.py`, keep its options, its scoring output and its exit codes, and register it on `eval_app` as `intake`. Import the new module from `src/devops_cli/commands/roadmap_eval.py` as the stage, implement and verify modules are imported. Leave no alias for the old name, and verify that `uv run devops ci test tests/commands/test_roadmap_eval_intake.py` passes

## 2. Exclude the moved command from MCP by its new path

Reads: `tests/ai/mcp/test_mcp.py`, `src/devops_cli/config/constants.py`. Changes: `tests/ai/mcp/test_mcp.py`.

- [ ] 2.1 Replace the entry `("roadmap", "intake-eval")` with `("roadmap", "eval", "intake")` in `mcp_command_exclusions` of `tests/ai/mcp/test_mcp.py`, and verify that `uv run devops ci test tests/ai/mcp/test_mcp.py` passes

## 3. Regenerate the command matrix and the command reference

Reads: `README.md`, `docs/commands/roadmap.md`, `src/devops_cli/commands/roadmap_eval_intake.py`. Changes: `README.md`, `docs/commands/roadmap.md`.

- [ ] 3.1 Run `uv run devops docs generate` and `uv run devops docs sync-readme` so the command matrix in `README.md` and the roadmap page `docs/commands/roadmap.md` list `devops roadmap eval intake` and drop `devops roadmap intake-eval`, and verify that `uv run devops ci docs` passes
- [ ] 3.2 README.md and docs/commands/roadmap.md hold the regenerated command text, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Check that no live file names the old command

Reads: `src/devops_cli/commands/roadmap.py`, `tests/ai/mcp/test_mcp.py`, `README.md`, `docs/commands/roadmap.md`. Changes: `src/devops_cli/commands/roadmap.py`.

- [ ] 4.1 Search the live files for the old name and fix each reference that is left, in the help text of the roadmap group or in a document. The changelog and the archived changes keep the old name as the record of a release and of a delivered change, and verify that `! git grep -n "intake-eval" src/ tests/ docs/ README.md` passes

## Criteria

- The CLI SHALL run the intake duplicate evaluation as `devops roadmap eval intake`.: group 1
- The CLI MUST NOT keep `devops roadmap intake-eval` as a command or as an alias.: group 1
- The moved command SHALL keep its `--dry-run` option and its scoring output.: group 1
- The command SHALL live in `src/devops_cli/commands/roadmap_eval_intake.py` and MUST be registered on `eval_app`.: group 1
- The MCP exclusion list MUST hold `("roadmap", "eval", "intake")` and no `("roadmap", "intake-eval")` entry.: group 2
- No live file SHALL name `intake-eval` after the change.: group 4
- The command matrix and the CLI reference SHALL list `devops roadmap eval intake` and MUST NOT list `devops roadmap intake-eval`.: group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

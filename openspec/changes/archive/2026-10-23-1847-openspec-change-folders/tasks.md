# Tasks

## 1. Readiness reads the archived change folder

- [x] 1.1 Write the grounding tests in `tests/test_pr_cmd.py` for each scenario of the `pr-grounding` delta, and verify that `uv run devops ci test tests/test_pr_cmd.py` fails on the base
- [x] 1.2 Add the archived grammar and the specs directory to `config/constants.py`, replace the task-file predicate and the base probe in `commands/pr.py`, and replace the task-file messages, and verify that `uv run devops ci test tests/test_pr_cmd.py tests/test_change_folders.py` passes
- [x] 1.3 Rewrite the help of `devops pr check-readiness`, run `devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 2. Delete the task files

- [x] 2.1 Write the decommission test in `tests/test_architectural_invariants.py`, and verify that it fails while `docs/agent/tasks/` is in the tree
- [x] 2.2 Delete `docs/agent/tasks/`, `tests/test_agent_task_files.py` and `tests/fixtures/task_files_baseline.txt`, remove the task-file entries of the docs inventory and of review routing, and rewrite the tests that used task-file paths as fixtures, and verify that `uv run devops ci test tests/test_architectural_invariants.py tests/test_docs_inventory.py tests/test_openspec_scaffold.py tests/test_review_path_routing.py tests/test_review_pr_post.py tests/test_consolidation_security_sanitizer.py` passes
- [x] 2.3 Rewrite AGENTS.md, the pull request template, `CONTEXT.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/TESTING.md`, `docs/agent/README.md`, `docs/_config.yml`, the knowledge base and the Loki values comment, and verify that `uv run devops ci test tests/test_agents_md_claims.py tests/test_docs_review_loop.py tests/test_instruction_generator.py` and `uv run devops docs check` pass

## 3. Validate the change

- [x] 3.1 Run `uv run devops openspec check` and verify that it passes

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

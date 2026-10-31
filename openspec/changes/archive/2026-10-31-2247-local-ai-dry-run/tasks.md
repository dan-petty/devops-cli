# Implementation Tasks

- [x] 1. Classify local AI commands in `src/devops_cli/commands/ai.py` with `@dry_run_class("no-external-request")` and remove echo-only previews and `--dry-run` options
- [x] 2. Classify `ai_ast` commands with `@dry_run_class("no-external-request")` and remove echo-only previews and `--dry-run` options
- [x] 3. Classify `ai_controller` commands with `@dry_run_class("no-external-request")` and ensure zero writes under dry run
- [x] 4. Classify `ai_harness` commands with `@dry_run_class("no-external-request")` and remove echo-only previews and `--dry-run` options
- [x] 5. Remove `dry_run` parameter and echo-only preview from `verify_architecture_spec` in `src/devops_cli/ai/spec/verifier.py`
- [x] 6. Remove all 20 commands from `tests/fixtures/dry_run_gaps.json`
- [x] 7. Update existing tests and create comprehensive test suite for all 20 commands
- [x] 8. Verify CI quality gates and sync CLI documentation

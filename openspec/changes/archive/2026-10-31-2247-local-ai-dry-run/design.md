# Design: Local AI Commands Dry-Run Behavior

## Architecture Overview
The dry-run classification system identifies commands that make no external network, cluster, or sub-process requests. These commands run safely during a dry run and carry the `no-external-request` class.

### Command Classification & Preview Removal
1. `src/devops_cli/commands/ai.py`:
   - Decorate with `@dry_run_class("no-external-request")`:
     - `ai_main` (app callback)
     - `config`
     - `bundle_models`
     - `token_count`
     - `spec_verify_cmd`
     - `repomap_cmd`
     - `audit_library_usage_cmd`
     - `pack_context_cmd`
     - `read_cmd`
     - `diagram_cmd`
     - `test_gen_cmd`
   - Remove `--dry-run` option and echo-only preview blocks (`render_dry_run_result`) from:
     - `spec_verify_cmd`
     - `repomap_cmd`
     - `audit_library_usage_cmd`
     - `pack_context_cmd`
     - `read_cmd`
     - `diagram_cmd`
     - `test_gen_cmd`

2. `src/devops_cli/commands/ai_ast.py`:
   - Decorate `ast_parse_cmd` and `ast_graph_cmd` with `@dry_run_class("no-external-request")`.
   - Remove `--dry-run` option and echo-only preview blocks from both commands.

3. `src/devops_cli/commands/ai_controller.py`:
   - Decorate `run_constellation_cmd`, `run_quiesce_cmd`, `run_failover_cmd`, and `run_resume_cmd` with `@dry_run_class("no-external-request")`.
   - In `run_quiesce_cmd`, `run_failover_cmd`, and `run_resume_cmd`, check `dry_run = dry_run or is_dry_run()` to ensure no snapshot writes occur under global dry run.

4. `src/devops_cli/commands/ai_harness.py`:
   - Decorate `harness_status`, `harness_offload`, and `harness_run` with `@dry_run_class("no-external-request")`.
   - Remove `--dry-run` option and echo-only preview blocks from `harness_offload` and `harness_run`.

5. `src/devops_cli/ai/spec/verifier.py`:
   - Remove `dry_run` parameter and `render_dry_run_result` block from `verify_architecture_spec`.

### Ratchet Inventory Update
Remove the 20 commands from `tests/fixtures/dry_run_gaps.json`:
- `ai`
- `ai ast graph`
- `ai ast parse`
- `ai audit-library-usage`
- `ai bundle-models`
- `ai config`
- `ai constellation`
- `ai diagram`
- `ai failover`
- `ai harness offload`
- `ai harness run`
- `ai harness status`
- `ai pack-context`
- `ai quiesce`
- `ai read`
- `ai repomap`
- `ai resume`
- `ai spec`
- `ai test-gen`
- `ai token-count`

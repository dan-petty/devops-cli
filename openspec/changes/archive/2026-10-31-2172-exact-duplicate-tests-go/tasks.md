# Tasks

## 1. Delete Exact Duplicates

- [x] Remove `test_diff_lines_carry_their_new_file_numbers` and `test_numbers_strip_back_to_the_original_text` from `tests/review/test_review_diff.py`
  - Verification: `grep -rn 'test_diff_lines_carry_their_new_file_numbers' tests/` returns 1 match; `grep -rn 'test_numbers_strip_back_to_the_original_text' tests/` returns 1 match
- [x] Remove `test_credentials_arrive_only_through_secret_devops_cli` from `tests/server/routes/test_k8s_roadmap_service.py`
  - Verification: `grep -rn 'test_credentials_arrive_only_through' tests/` returns 1 match

## 2. Parametrize Near-Duplicate Groups

- [x] Parametrize malformed PromQL tests in `tests/commands/test_promql_analysis.py`
  - Verification: `uv run pytest tests/commands/test_promql_analysis.py`
- [x] Parametrize secret resolution order tests in `tests/security/test_secret_resolution.py`
  - Verification: `uv run pytest tests/security/test_secret_resolution.py`
- [x] Parametrize branch protection error tests in `tests/github/test_github_branch_protection.py`
  - Verification: `uv run pytest tests/github/test_github_branch_protection.py`
- [x] Parametrize think block stripping tests in `tests/ai/test_thinking.py`
  - Verification: `uv run pytest tests/ai/test_thinking.py`
- [x] Parametrize query validation failures in `tests/commands/k8s/test_stack_dashboards.py`
  - Verification: `uv run pytest tests/commands/k8s/test_stack_dashboards.py`
- [x] Parametrize binary resolution in `tests/commands/test_tf.py`
  - Verification: `uv run pytest tests/commands/test_tf.py`
- [x] Parametrize refused arguments in `tests/commands/test_install_tools.py`
  - Verification: `uv run pytest tests/commands/test_install_tools.py`
- [x] Parametrize schemeless URLs in `tests/commands/test_config_field_validation.py`
  - Verification: `uv run pytest tests/commands/test_config_field_validation.py`
- [x] Parametrize unsupported provider sampling options in `tests/ai/test_ai_model_sampling.py`
  - Verification: `uv run pytest tests/ai/test_ai_model_sampling.py`
- [x] Parametrize missing binary checks in `tests/ai/mcp/test_docker_cosign.py`
  - Verification: `uv run pytest tests/ai/mcp/test_docker_cosign.py`
- [x] Parametrize CLI fast dispatch in `tests/dry_run/test_fast_dispatch.py`
  - Verification: `uv run pytest tests/dry_run/test_fast_dispatch.py`

## 3. Verify Test Count and CI Quality Gates

- [x] Confirm total collected test items equals 14746 (14749 - 3)
  - Verification: `uv run pytest --collect-only -q`
- [x] Run full test suite and quality gates
  - Verification: `uv run devops ci`

# Tasks

## 1. Add Assertions to No-Assertion Tests

- [x] Add assertions to `tests/commands/test_argo.py` (`test_valid_k8s_label_names`, `test_valid_k8s_resource_names`)
  - Verification: `uv run pytest tests/commands/test_argo.py -k "test_valid_k8s"`
- [x] Add assertions to `tests/http/test_http_connection_pool.py` (`test_closing_an_empty_registry_is_harmless`)
  - Verification: `uv run pytest tests/http/test_http_connection_pool.py -k "test_closing_an_empty_registry_is_harmless"`
- [x] Add assertions to `tests/k8s/test_k8s_security_stream.py` (`test_render_security_alerts_empty`)
  - Verification: `uv run pytest tests/k8s/test_k8s_security_stream.py -k "test_render_security_alerts_empty"`
- [x] Add assertions to `tests/ai/test_output.py` (`test_print_panel_fallback_on_exception`)
  - Verification: `uv run pytest tests/ai/test_output.py -k "test_print_panel_fallback_on_exception"`
- [x] Add assertions to `tests/ai/review/test_review_runner.py` (`test_rendering_helpers`)
  - Verification: `uv run pytest tests/ai/review/test_review_runner.py -k "test_rendering_helpers"`
- [x] Add assertions to `tests/commands/test_vault_cmd.py` (`test_validate_vault_path_valid`)
  - Verification: `uv run pytest tests/commands/test_vault_cmd.py -k "test_validate_vault_path_valid"`

## 2. Update Built-in Exception Raises Sites with Match or Exit Code

- [x] Add `match=` or `exc.value.code` checks to identified `pytest.raises` sites
  - Verification: `grep -rn 'pytest.raises' tests/` checks
- [x] Configure Ruff `PT011` `raises-require-match-for` in `pyproject.toml`
  - Verification: `uv run ruff check tests/`

## 3. Add AST-Grep Rule and Pass Quality Gates

- [x] Add ast-grep rule and test in `.ast-grep/rules/` and `.ast-grep/rule-tests/`
  - Verification: `uv run ast-grep test --skip-snapshot-tests`
- [x] Verify scratch case triggers PT011 failure
  - Verification: `uv run ruff check --select PT011`
- [x] Run full CI quality suite
  - Verification: `uv run devops ci`

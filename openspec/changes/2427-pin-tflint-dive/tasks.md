# Tasks

## 1. tflint

- [x] 1.1 Write the failing tests. The lock pins tflint as four zip builds (`tests/test_tools_lock.py`). The installer unpacks a zip build and refuses a zip without the member (`tests/test_install_tools.py`). Each scanner of the registry has a pinned program (`tests/test_scanner_contract.py`). A scan without tflint is `unavailable` and has no finding, and the parser reads the report in the shape of the tflint source (`tests/security/test_tflint.py`). `devops tf lint` exits 1 when tflint did not run (`tests/test_tf.py`), and `tf_lint` replies with the outcome (`tests/test_builtin_tools.py`). Verify with `uv run devops ci test tests/test_tools_lock.py tests/test_install_tools.py tests/test_scanner_contract.py tests/security/test_tflint.py tests/test_tf.py tests/test_builtin_tools.py`
- [x] 1.2 Pin tflint 0.65.0 in `src/devops_cli/tools_lock/tools.lock`, add the format `zip` to `src/devops_cli/tools_lock/__init__.py` and to the installer, and add a note on it to the header of the lock. Verify with `uv run devops ci test tests/test_tools_lock.py tests/test_install_tools.py`
- [x] 1.3 Delete the fallback and `has_builtin_patterns` of `src/devops_cli/security/tflint.py`, and their tests, including `test_tflint_fallback_skips_symlinks`. Make `devops tf lint` report a lint that did not run, and make `tf_lint` run the adapter through `_run_adapter_scan`. Update `tests/fixtures/swallowed_failures_ceilings.json`. Verify with `uv run devops ci test tests/security/test_tflint.py tests/test_tf.py tests/test_builtin_tools.py tests/test_security_sandbox_and_protection.py tests/test_scanner_contract.py`
- [x] 1.4 Name the pinned version on the knowledge base page `src/devops_cli/ai/knowledge_base/it_domains/tools/tflint.md`. Verify with `uv run devops ci test tests/test_kb_manuals_metadata.py`

## 2. dive

- [x] 2.1 Write the failing tests: the registry holds 13 scanners and none is `dive`, `devops docker` has no `analyze-layers`, and the agent tools have no `docker_analyze_layers` (`tests/security/test_scanner_base_and_registry.py`, `tests/test_docker.py`, `tests/test_builtin_tools.py`). Verify with `uv run devops ci test tests/security/test_scanner_base_and_registry.py tests/test_docker.py tests/test_builtin_tools.py`
- [x] 2.2 Delete `src/devops_cli/security/dive.py`, the dive scanner of the registry and of `security/__init__.py`, the command `devops docker analyze-layers`, the agent tool `docker_analyze_layers`, `DEFAULT_DIVE_MIN_EFFICIENCY`, `DEFAULT_DIVE_MAX_WASTED_BYTES`, the help, message and model strings that only dive read, and the tests of dive (`tests/test_security_dive.py` and the dive cases of other files). Verify with `uv run devops ci test tests/security tests/test_docker.py tests/test_builtin_tools.py tests/test_mcp.py tests/test_cli_format_adoption.py tests/test_resource_schemas.py tests/test_scan_outcomes_and_gating.py tests/test_security_sandbox_and_protection.py`
- [x] 2.3 Delete the knowledge base page of dive and its index entries, and give the knowledge base counts of `tests/test_kb.py` and `tests/test_kb_manuals_metadata.py` one page less. Regenerate the documents. Verify with `uv run devops docs generate --sync-readme`, `uv run devops docs check` and `uv run devops ci test tests/test_kb.py tests/test_kb_manuals_metadata.py tests/test_docs.py`

## Workflow follow-up

- Pending a person: record the run of the pinned tflint that `tests/fixtures/scanner_runs/runs_with_findings.json` needs, with the command of the adapter, and have the contract test read its version. `design.md` gives the commands.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

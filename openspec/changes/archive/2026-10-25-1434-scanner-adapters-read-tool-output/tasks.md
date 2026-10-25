# Tasks

## 1. Gitleaks

- [x] 1.1 Record a Gitleaks 8.30.1 run that finds a GitHub token, with the new command and `--redact`, into `tests/fixtures/scanner_runs/runs_with_findings.json`, and give `ScannerFake` `script_run_with_findings` to answer with it. Write the failing tests: a leak is a finding of a scan that ran (`tests/test_security_gitleaks.py`), the agent tool `scan_gitleaks` reports it, the builder makes `dir` and `git` with `--report-path -` and `--redact` (`tests/test_command_builders.py`), and a review's run has the new argument template (`tests/test_review_tool_runs.py`). Verify with `uv run devops ci test tests/test_security_gitleaks.py tests/test_command_builders.py tests/test_review_tool_runs.py`
- [x] 1.2 Change `build_gitleaks_cmd` in `src/devops_cli/config/commands.py`, and record the contract run of the clean scan again through the adapter with the real tool. Verify with `uv run devops ci test tests/test_security_gitleaks.py tests/test_scanner_contract.py tests/test_review_tool_runs.py`
- [x] 1.3 Show `gitleaks dir` and `--report-path -` in `src/devops_cli/ai/knowledge_base/it_domains/tools/gitleaks.md`. Verify with `uv run devops ci test tests/test_docs.py`

## 2. Popeye

- [x] 2.1 Record a Popeye 0.22.1 run at warn level over one namespace into the same fixture, cut to three sections and two resources, with the names of the cluster and the context as `example`. Write the failing tests: each issue is a finding at its linter, resource and container (`tests/test_secops.py`), the command carries `-l warn` and the namespace, the agent tool `scan_popeye` runs the adapter (`tests/test_builtin_tools.py`), and the shared Popeye sample has the 0.22 shape (`tests/test_consolidation_security_scanner_base.py`). Verify with `uv run devops ci test tests/test_secops.py tests/test_builtin_tools.py tests/test_consolidation_security_scanner_base.py`
- [x] 2.2 Change `build_popeye_cmd`, add `CONST_POPEYE_RESOURCE_GROUPS` to `src/devops_cli/config/constants.py`, pass the namespace in `PopeyeScanner.build_command`, rewrite the parser for `popeye.sections` in `src/devops_cli/security/popeye.py`, and make `scan_popeye` run the adapter. Delete the parser of `sanitizers` and the old Popeye tests. Verify with `uv run devops ci test tests/test_secops.py tests/test_builtin_tools.py tests/test_command_builders.py`
- [x] 2.3 Show `-l warn` in `src/devops_cli/ai/knowledge_base/it_domains/tools/kubelinter_popeye_pluto.md`. Verify with `uv run devops ci test tests/test_docs.py`

## 3. Pluto

- [x] 3.1 Record a Pluto 5.24.4 run over two removed APIs, one with no replacement, into the same fixture. Write the failing tests: the findings name the object, the API, the release and the replacement, or say that none exists; a review's run names the manifest relative to its scratch directory; a `filePath` with `..` names the manifest (`tests/test_secops.py`); and the builder names a target relative to `cwd` (`tests/test_command_builders.py`). Give the Pluto samples of `tests/test_consolidation_security_scanner_base.py` and `tests/test_review_security_tools.py` the keys that Pluto writes. Verify with `uv run devops ci test tests/test_secops.py tests/test_command_builders.py`
- [x] 3.2 Pass `cwd` to `build_command` in `src/devops_cli/security/base.py`, name the target relative to it in `build_pluto_cmd`, make `manifest_location` of `src/devops_cli/security/kubelinter.py` public, and rewrite the Pluto parser without invented values. Delete the old Pluto tests. Verify with `uv run devops ci test tests/test_secops.py tests/test_review_security_tools.py tests/test_consolidation_security_scanner_base.py tests/test_scanner_contract.py tests/ai/review/test_pipeline.py`
- [x] 3.3 Regenerate the documents. Verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- kubeconform and Checkov are not in `tools.lock`, so their adapters run hand-written fallbacks and misread the tool when a person installs it: #2214.
- `devops scan secrets --json` and the other scan commands print their progress line on stdout before the JSON: #2216.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

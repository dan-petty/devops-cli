# Tasks

## 1. Make security_status and status required

Reads: none. Changes: `src/devops_cli/models/vulnerability.py`, `tests/models/test_resource_schemas.py`, `tests/review/test_report.py`, `tests/security/test_osv_scanner.py`, `tests/security/test_reference_report_order.py`, `tests/security/test_vulnerability_lookup.py`, `tests/ai/test_review_finding_losses.py`, `tests/ai/review/test_review_report_summary.py`, `tests/ai/review/test_review_pipeline.py`.

- [ ] 1.1 Write a test in `tests/models/test_resource_schemas.py` that constructs NetworkReference(target='203.0.113.7') without security_status and asserts a pydantic ValidationError is raised. Write a test that constructs PackageLookupResult() without status and asserts a pydantic ValidationError is raised, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` fails on the base
- [ ] 1.2 In `src/devops_cli/models/vulnerability.py`, remove the default from the annotation `security_status: str = "✓ Safe"` of NetworkReference, so that it reads `security_status: str`. Remove the default from the annotation `status: str = "ok"  # "ok" | "failed"` of PackageLookupResult in the same file, so that it reads `status: str  # "ok" | "failed"`. Both fields are plain annotations, not `Field` calls, so a field with no default is required. Verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes
- [ ] 1.3 Set `security_status="✓ Safe"` (the value that the removed default gave) at each NetworkReference call in these test files that omits it: `tests/review/test_report.py` line 160, `tests/security/test_osv_scanner.py` line 349, `tests/security/test_reference_report_order.py` line 28, `tests/security/test_vulnerability_lookup.py` line 593, `tests/ai/test_review_finding_losses.py` line 47, `tests/ai/review/test_review_report_summary.py` lines 231 and 232, `tests/ai/review/test_review_pipeline.py` lines 782 and 783. These are 9 calls in 7 files. Verify that `uv run devops ci test tests/review/test_report.py tests/security/test_osv_scanner.py tests/security/test_reference_report_order.py tests/ai/test_review_finding_losses.py tests/ai/review/test_review_report_summary.py tests/ai/review/test_review_pipeline.py` passes
- [ ] 1.4 Rewrite `test_package_lookup_result_defaults` in `tests/security/test_vulnerability_lookup.py`. Its call at line 717 omits status, and the test asserts the removed default "ok". Build `PackageLookupResult(status="ok")` and assert that vulnerabilities is `[]` and reason is `""`. Rename the test to `test_package_lookup_result_list_and_reason_defaults`. Verify that `uv run devops ci test tests/security/test_vulnerability_lookup.py` passes
- [ ] 1.5 Run `grep -rlE "NetworkReference\(|PackageLookupResult\(" tests` and check that every test file it lists is in the next command. A test call that still omits a required field fails with a ValidationError. Verify that `uv run devops ci test tests/models/test_resource_schemas.py tests/review/test_report.py tests/security/test_osv_scanner.py tests/security/test_reference_report_order.py tests/security/test_vulnerability_lookup.py tests/security/test_builtin_tools.py tests/ai/test_review_finding_losses.py tests/ai/review/test_review_report_summary.py tests/ai/review/test_review_pipeline.py tests/ai/review/test_review_runner.py tests/ai/review/test_review_admission.py tests/ai/review/test_review_console_report.py` passes

## 2. Remove test references to deleted models

Reads: none. Changes: `tests/models/test_resource_schemas.py`.

- [ ] 2.1 In `tests/models/test_resource_schemas.py`, remove `NetworkIntelResult` and `PackageIntelResult` from the import list of `devops_cli.models.security` (lines 80 and 82 on `main`). In `test_security_resource_models_roundtrip`, remove the statement `pkg_res = PackageIntelResult(...)` and the line `assert pkg_res.is_vulnerable is False` after it (lines 270 to 277). Remove the statement `net_res = NetworkIntelResult(...)` and the line `assert net_res.is_malicious is False` after it (lines 281 to 289). Keep every other line of the test, including the `PackageIntelRequest` and `NetworkIntelRequest` checks. Verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes

## 3. Remove NetworkIntelResult and PackageIntelResult

Reads: none. Changes: `src/devops_cli/models/security.py`, `src/devops_cli/models/__init__.py`.

- [ ] 3.1 Write a test in `tests/models/test_resource_schemas.py` that asserts importing NetworkIntelResult from devops_cli.models raises ImportError. Write a test that asserts importing PackageIntelResult from devops_cli.models raises ImportError. Write a test that asserts neither name is in `devops_cli.models.__all__`, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` fails on the base
- [ ] 3.2 Delete the NetworkIntelResult class from `src/devops_cli/models/security.py`. Delete the PackageIntelResult class from `src/devops_cli/models/security.py`. Remove both names from the import list in `src/devops_cli/models/__init__.py`. Remove both names from the __all__ list in `src/devops_cli/models/__init__.py` (lines 247 and 251 on `main`), and verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes

## 4. Archive

Reads: none. Changes: `openspec/changes/`.

- [ ] 4.1 In the last commit, archive the change with `uv run devops openspec archive 2636-a-result-that-no-lookup-marked`, and verify that `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

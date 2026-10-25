# Tasks

## 1. Manifest Object Extraction and Key Formatting

- [x] 1.1 Write tests in `tests/test_review_manifests.py` for `manifest_object_key`, `read_manifest_objects` with `List` items, and `collect_manifest_objects`. Verify failure with `uv run devops ci test tests/test_review_manifests.py`.
- [x] 1.2 Implement `manifest_object_key`, `read_manifest_objects`, and `collect_manifest_objects` in `src/devops_cli/review/manifests.py`. Verify with `uv run devops ci test tests/test_review_manifests.py`.

## 2. Location Validation and Empty Physical Path Support

- [x] 2.1 Add tests to `tests/test_review_admission.py` for empty physical path location handling and `object-not-in-commit` rejection. Verify failure with `uv run devops ci test tests/test_review_admission.py`.
- [x] 2.2 Update `validate_location()` in `src/devops_cli/review/location.py` to evaluate empty-path findings with logical locations and reject absent manifest objects. Verify with `uv run devops ci test tests/test_review_admission.py`.

## 3. Scanner Adapters and Pipeline Admission Wiring

- [x] 3.1 Update `src/devops_cli/security/kubelinter.py` and `src/devops_cli/security/pluto.py` to use `manifest_object_key`. Verify with `uv run devops ci test tests/test_secops.py`.
- [x] 3.2 Wire `manifest_objects` through `_admit_scanner_findings()` and `_admit_single_candidate()` in `src/devops_cli/ai/review/pipeline.py`. Verify with `uv run devops ci test tests/ai/review/test_pipeline.py`.
- [x] 3.3 Migrate `tests/test_review_admission.py:129` to use `manifest_object_key`. Verify with `uv run devops ci test tests/test_review_admission.py`.

## 4. Verification and Documentation

- [x] 4.1 Update documentation with `uv run devops docs generate --sync-readme`.
- [x] 4.2 Verify static analysis, linting, tests, and coverage with `uv run devops ci`.

## Workflow follow-up

- `lockfile_packages` stays unset until a scanner emits `name@version` locators.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

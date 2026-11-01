# Tasks

## 1. Make security_status and status required

Reads: none. Changes: `src/devops_cli/models/vulnerability.py`.

- [ ] 1.1 Write a test in `tests/models/test_resource_schemas.py` that constructs NetworkReference(target='203.0.113.7') without security_status and asserts a pydantic ValidationError is raised. Write a test that constructs PackageLookupResult() without status and asserts a pydantic ValidationError is raised, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` fails on the base
- [ ] 1.2 Remove the default value from NetworkReference.security_status in `src/devops_cli/models/vulnerability.py`. Change the Field to use `...` as the first argument so the field is required. Remove the default value from PackageLookupResult.status in the same file. Change the Field to use `...` as the first argument so the field is required, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes

## 2. Remove test references to deleted models

Reads: none. Changes: `tests/models/test_resource_schemas.py`.

- [ ] 2.1 Remove all test functions and fixtures in `tests/models/test_resource_schemas.py` that construct or reference NetworkIntelResult or PackageIntelResult. Remove any import of those names from the test file, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes

## 3. Remove NetworkIntelResult and PackageIntelResult

Reads: none. Changes: `src/devops_cli/models/security.py`, `src/devops_cli/models/__init__.py`.

- [ ] 3.1 Write a test in `tests/models/test_resource_schemas.py` that asserts importing NetworkIntelResult from devops_cli.models raises ImportError. Write a test that asserts importing PackageIntelResult from devops_cli.models raises ImportError, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` fails on the base
- [ ] 3.2 Delete the NetworkIntelResult class from `src/devops_cli/models/security.py`. Delete the PackageIntelResult class from `src/devops_cli/models/security.py`. Remove both names from the import list in `src/devops_cli/models/__init__.py`. Remove both names from the __all__ list in `src/devops_cli/models/__init__.py`, and verify that `uv run devops ci test tests/models/test_resource_schemas.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

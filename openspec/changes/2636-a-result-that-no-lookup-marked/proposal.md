# Proposal

## Why

#2636 reports that four models in src/devops_cli/models/ default to a clean security status. A producer that forgets to set the field gives a result that reads as safe, with no error. This is the same defect shape as #2504, which fixed one model and left these four.

## What Changes

- NetworkReference.security_status has no default value; a missing field raises a ValidationError
- PackageLookupResult.status has no default value; a missing field raises a ValidationError
- NetworkIntelResult is removed from src/devops_cli/models/security.py
- PackageIntelResult is removed from src/devops_cli/models/security.py
- The models package __all__ no longer lists the two removed models
- tests/models/test_resource_schemas.py no longer references the removed models
- Nine existing NetworkReference test calls in seven test files set security_status, because the field is now required
- One existing PackageLookupResult test call sets status, and test_package_lookup_result_defaults no longer asserts the removed default
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `threat-intel-lookup-outcome`: NetworkReference security_status is required, PackageLookupResult status is required, NetworkIntelResult is removed, PackageIntelResult is removed

## Impact

- Code: `src/devops_cli/models/vulnerability.py`, `src/devops_cli/models/security.py`, `src/devops_cli/models/__init__.py`
- Tests: `tests/models/test_resource_schemas.py`, `tests/review/test_report.py`, `tests/security/test_osv_scanner.py`, `tests/security/test_reference_report_order.py`, `tests/security/test_vulnerability_lookup.py`, `tests/ai/test_review_finding_losses.py`, `tests/ai/review/test_review_report_summary.py`, `tests/ai/review/test_review_pipeline.py`

## Feasibility

Run on `origin/main` at commit `5ac0bea4`, with pydantic 2.13.5 (`pyproject.toml` pins `pydantic==2.13.5`). In pydantic v2, a field annotation with no default is required, so removing the default is enough.

Check 1: the two fields are plain annotations with a clean default, and are not required.

```text
$ grep -nE '^    (security_)?status: str = ("ok"|"✓ Safe")' src/devops_cli/models/vulnerability.py
54:    status: str = "ok"  # "ok" | "failed"
79:    security_status: str = "✓ Safe"
$ uv run python -c "import pydantic; print(pydantic.VERSION)"
2.13.5
$ uv run python -c "from devops_cli.models.vulnerability import NetworkReference, PackageLookupResult; print(NetworkReference(target='203.0.113.7').security_status, PackageLookupResult().status)"
✓ Safe ok
$ uv run python -c "from devops_cli.models.vulnerability import NetworkReference, PackageLookupResult; print(NetworkReference.model_fields['security_status'].is_required(), PackageLookupResult.model_fields['status'].is_required())"
False False
```

Check 2: the two intel models exist, have clean defaults, and nothing in `src/` outside the models package uses them.

```text
$ uv run python -c "from devops_cli.models.security import NetworkIntelResult, PackageIntelResult; print(NetworkIntelResult(target='x').reputation_summary, PackageIntelResult(package_name='x').security_status)"
Safe Clean
$ grep -rnE "NetworkIntelResult|PackageIntelResult" src
src/devops_cli/models/__init__.py:125:    NetworkIntelResult,
src/devops_cli/models/__init__.py:127:    PackageIntelResult,
src/devops_cli/models/__init__.py:247:    "NetworkIntelResult",
src/devops_cli/models/__init__.py:251:    "PackageIntelResult",
src/devops_cli/models/security.py:60:class PackageIntelResult(BaseModel):
src/devops_cli/models/security.py:80:class NetworkIntelResult(BaseModel):
$ grep -rnE "NetworkIntelResult|PackageIntelResult" tests docs *.md k8s
tests/models/test_resource_schemas.py:80:    NetworkIntelResult,
tests/models/test_resource_schemas.py:82:    PackageIntelResult,
tests/models/test_resource_schemas.py:270:    pkg_res = PackageIntelResult(
tests/models/test_resource_schemas.py:281:    net_res = NetworkIntelResult(
```

Check 3: every call site of the two required-field models. An AST scan of `src` and `tests` (a script in `.data/agent/scratch/`) lists each `NetworkReference(...)` and `PackageLookupResult(...)` call and flags a call that omits `security_status` or `status`. No `**kwargs` call exists. No `model_validate` call exists for the two models.

```text
src: 8 calls, all set the field
  src/devops_cli/security/reference_extractor.py 547, 576, 589   NetworkReference
  src/devops_cli/security/vulnerability_lookup.py 154, 191, 256, 282, 305   PackageLookupResult
tests: 28 calls set the field, 10 calls omit it
  tests/ai/review/test_review_pipeline.py 782 NetworkReference
  tests/ai/review/test_review_pipeline.py 783 NetworkReference
  tests/ai/review/test_review_report_summary.py 231 NetworkReference
  tests/ai/review/test_review_report_summary.py 232 NetworkReference
  tests/ai/test_review_finding_losses.py 47 NetworkReference
  tests/review/test_report.py 160 NetworkReference
  tests/security/test_osv_scanner.py 349 NetworkReference
  tests/security/test_reference_report_order.py 28 NetworkReference
  tests/security/test_vulnerability_lookup.py 593 NetworkReference
  tests/security/test_vulnerability_lookup.py 717 PackageLookupResult
```

The 10 calls need a change in group 1 of `tasks.md`. The `src/` change is safe, because no `src/` call omits a field.

## Existing Tool Considered

No open, maintained tool or library covers the need to fix Pydantic model defaults in this project. The fix is a code change to the project's own models. The written cost is the tokens to change two field definitions, remove two unused classes, update the package exports, and update the test file.

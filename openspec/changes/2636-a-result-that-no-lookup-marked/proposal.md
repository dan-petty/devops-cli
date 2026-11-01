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
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `threat-intel-lookup-outcome`: NetworkReference security_status is required, PackageLookupResult status is required, NetworkIntelResult is removed, PackageIntelResult is removed

## Impact

- Code: `src/devops_cli/models/vulnerability.py`, `src/devops_cli/models/security.py`, `src/devops_cli/models/__init__.py`
- Tests: `tests/models/test_resource_schemas.py`

## Feasibility

- The context shows NetworkIntelResult at line 80 and PackageIntelResult at line 60 of src/devops_cli/models/security.py, and the identifier matches confirm both names in src/devops_cli/models/__init__.py at lines 125, 127, 247, 251.
- The issue cites src/devops_cli/models/vulnerability.py for NetworkReference.security_status and PackageLookupResult.status, and the #2504 design doc confirms the same file holds those models.
- The issue states no code in src/ uses the two intel models; only tests/models/test_resource_schemas.py builds them.
- First check: run `uv run python -c "from devops_cli.models.vulnerability import NetworkReference, PackageLookupResult; print(NetworkReference(target='203.0.113.7').security_status, PackageLookupResult().status)"` to confirm the clean defaults.
- Second check: run `uv run python -c "from devops_cli.models.security import NetworkIntelResult, PackageIntelResult; print(NetworkIntelResult(target='x').reputation_summary, PackageIntelResult(package_name='x').security_status)"` to confirm the unused models exist.

## Existing Tool Considered

No open, maintained tool or library covers the need to fix Pydantic model defaults in this project. The fix is a code change to the project's own models. The written cost is the tokens to change two field definitions, remove two unused classes, update the package exports, and update the test file.

# Proposal

## Why

Issue #2600 asks whether the two product readers (devops scan complexity and the inspection hotspots) should take their complexity figure from Ruff at run time, or keep the hand-written McCabe port with a stated reason. The decision is to keep the port: Ruff is a dev dependency, its JSON output has no structured complexity field, and the port is 90 lines of pure Python already tested to match Ruff's C901.

## What Changes

- Record the decision to keep the McCabe port with the stated reason in the module docstring of core/code_metrics.py
- Add a spec requirement that documents the single-source complexity behavior of devops scan complexity and the inspection hotspots
- Verify the existing 12-sample test holds the port equal to Ruff's C901
- The change fits one pull request.

## Capabilities

### New Capabilities

- `code-complexity-metrics`: single-source-complexity

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/code_metrics.py`

## Feasibility

- The premise is confirmed: pyproject.toml lists ruff in [dependency-groups] dev, not in [project] dependencies, so Ruff is not a runtime dependency.
- src/devops_cli/core/code_metrics.py exists at 119 lines with the mccabe_complexity function and the FunctionComplexity dataclass.
- tests/test_code_metrics.py holds 12 parametrized samples that compare the port to Ruff's C901.
- The two readers (security/complexity.py and ai/inspection.py) import from core/code_metrics.py, as stated in the issue body.
- First check the implementation runs: uv run devops ci test tests/test_code_metrics.py confirms all 12 samples pass and the port matches Ruff's C901.

## Existing Tool Considered

Ruff C901 computes the same standard McCabe count. It is a dev dependency only (pyproject.toml [dependency-groups] dev). Its JSON output embeds the complexity number in a diagnostic message string, not a structured field. The port costs about 90 lines of Python and 12 test samples to build, keep and fix. No internal code is deleted.

# Proposal

## Why

Issue #1437: `devops tf drift` reads the local state file directly through `load_state`.
The state file is not a public interface of OpenTofu or Terraform.
Direct file reading causes four defects:
- OpenTofu client-side state encryption writes state files without a `resources` key, so encrypted state reads as empty.
- Module resources have module-scoped addresses in state, so drift reports them as orphaned.
- Resource provider names are guessed from type prefixes, so aliased providers are misreported.
- Drift detection only checks structural addresses and misses attribute drift against live infrastructure.

## What Changes

- State inspection reads state through `tofu show -json` when a directory is initialized.
- Drift detection reads attribute drift through `tofu plan -refresh-only -json`.
- An uninitialized directory reports that state is unavailable and names `tofu init`.
- Delete `load_state`, `_project_state_resource`, `resolve_state_file`, and the prefix-based provider guess.
- Keep in-process HCL parsing for resource dependency graphs and blast radius analysis.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `terraform-state-drift`: State inspection and drift detection through OpenTofu CLI interfaces.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/tf/analysis.py`, `src/devops_cli/commands/tf.py`, `src/devops_cli/models/tf.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_tf_analysis.py`, `tests/test_tf.py`.

## Feasibility

- Confirmed against OpenTofu 1.9.0 documentation and CLI behavior.
- `tofu show -json` is the public machine-readable interface representing state and decrypting client-side encrypted state.
- `tofu plan -refresh-only -json` detects attribute drift against live infrastructure without changing state.
- Direct state file inspection misreports encrypted state as empty and misses child module declarations because `parse_hcl_directory` reads only root files.

## Existing Tool Considered

OpenTofu CLI tools `tofu show -json` and `tofu plan -refresh-only -json` cover state inspection and live drift detection.
OpenTofu is the standard open tool.
This change deletes internal code: `load_state`, `_project_state_resource`, `resolve_state_file`, and the prefix-based provider guess in `src/devops_cli/tf/analysis.py`.

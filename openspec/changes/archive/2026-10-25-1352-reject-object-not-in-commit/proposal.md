# Proposal

## Why

Issue #1352 identifies that review admission does not receive manifest objects from the reviewed revision. Static scanner findings that name absent Kubernetes objects are admitted rather than rejected with `object-not-in-commit`. Findings with only a logical location are also rejected early for an empty physical path. This change supplies manifest objects to admission and validates logical locations against them.

This change fits in one pull request.

## What Changes

- Add a shared helper to construct Kubernetes object keys in canonical `Kind/namespace/name` or `Kind/name` format.
- Update Kube-linter and Pluto scanner adapters to format logical locations with the shared key helper.
- Read Kubernetes manifest objects from the reviewed revision YAML files using `yaml.safe_load_all`, including `List` items.
- Pass the manifest objects to admission in the review pipeline and base revision collection.
- Permit findings with only a logical location to reach logical location validation in `validate_location`.
- Reject findings that name absent Kubernetes objects as `object-not-in-commit`.
- Migrate `tests/test_review_admission.py` to use the shared key helper.

This change alters externally observable review finding admission and rejection behavior, so it carries a spec delta.

## Capabilities

### New Capabilities
- `review-manifest-admission`: Admission gate validation for Kubernetes manifest object locations in review findings.

### Modified Capabilities

## Impact

- `src/devops_cli/review/manifests.py`: New module defining manifest object key construction and document parsing.
- `src/devops_cli/review/location.py`: Allow empty physical paths when a logical location is present.
- `src/devops_cli/review/admission.py`: Admit findings with matching manifest objects.
- `src/devops_cli/security/kubelinter.py`: Use shared key construction helper.
- `src/devops_cli/security/pluto.py`: Use shared key construction helper.
- `src/devops_cli/ai/review/pipeline.py`: Pass manifest objects into admission calls.
- `tests/test_review_admission.py`: Test manifest object admission, rejection, and key formatting.

## Feasibility

The premise was confirmed by inspecting `src/devops_cli/ai/review/pipeline.py` and `src/devops_cli/review/location.py`. `_admit_single_candidate` did not pass `manifest_objects` to `admit()`. Line 77 in `location.py` rejected findings with empty paths before checking logical locations. PyYAML 6.0+ is installed and provides `yaml.safe_load_all` for multi-document streams. The system supports the requested behavior without architectural blockers.

## Existing Tool Considered

We considered delegating manifest object extraction to `kubectl` or `kubeconform`. `kubectl` requires a live cluster binary and external process execution. `kubeconform` validates schemas but does not expose a lightweight Python API for object indexing. Standard PyYAML (`yaml.safe_load_all`) is already a project dependency. It provides fast in-process parsing with zero added binary dependencies.

Internal redundant code deleted: custom string formatting in `kubelinter.py` and `pluto.py` is replaced by the unified helper.

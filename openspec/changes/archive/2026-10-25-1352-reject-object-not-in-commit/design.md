# Design

## Context

See proposal.md - Why. The review engine admits findings through `admit()` in `src/devops_cli/review/admission.py`. `validate_location()` in `src/devops_cli/review/location.py` checks finding physical paths and logical locations. Currently `manifest_objects` is not populated during scanner admission in `src/devops_cli/ai/review/pipeline.py`.

## Goals / Non-Goals

**Goals:**
- Provide a unified helper `manifest_object_key(kind, name, namespace=None)` in `src/devops_cli/review/manifests.py`.
- Provide `read_manifest_objects(content)` in `src/devops_cli/review/manifests.py` using `yaml.safe_load_all`, unwrapping `List` items.
- Provide `collect_manifest_objects(manifest_paths, content_getter=None)` to collect all manifest object keys across reviewed files.
- Wire `manifest_objects` into `_admit_scanner_findings()` and `_admit_single_candidate()` in `src/devops_cli/ai/review/pipeline.py`.
- Allow findings with empty physical paths and non-empty logical locations to reach logical location validation in `validate_location()`.
- Validate logical locations against `manifest_objects` and reject missing objects as `object-not-in-commit`.
- Use `manifest_object_key` in `kubelinter.py` and `pluto.py`.
- Migrate `tests/test_review_admission.py` to use `manifest_object_key`.

**Non-Goals:**
- Populate `lockfile_packages`. Per issue 1352 acceptance criteria, `lockfile_packages` remains unset until scanners emit `name@version` locators.
- Parse Helm templates or run dynamic template evaluation. Only static YAML manifests are parsed.

## Decisions

### Decision: Module placement for manifest object extraction and key formatting
Create a new module `src/devops_cli/review/manifests.py` containing `manifest_object_key()`, `read_manifest_objects()`, and `collect_manifest_objects()`.
- *Rationale*: Key creation and manifest document inspection are domain functions of the review system. Placing them in `devops_cli.review.manifests` keeps `admission.py` and `location.py` concise and prevents circular dependencies with scanner adapters.
- *Alternatives considered*:
  - Placing helpers in `src/devops_cli/security/kubeconform.py`. Rejected because `kubeconform.py` is a security scanner adapter, whereas review admission and location validation belong to `devops_cli.review`.
  - Placing helpers in `src/devops_cli/review/location.py`. Rejected to maintain separation of location checking from multi-document YAML parsing.

### Decision: Key format for Kubernetes objects
Format the key as `f"{kind}/{namespace}/{name}"` when namespace is non-empty, and `f"{kind}/{name}"` when namespace is absent or empty.
- *Rationale*: Kube-linter already uses this format. Pluto and manifest inspection will use this identical function to guarantee key parity.
- *Alternatives considered*:
  - Always including a default namespace such as `default`. Rejected because manifests and scanners omit namespaces for cluster-scoped resources or un-namespaced manifests, and acceptance criteria specifically require `Deployment/web` when un-namespaced.

### Decision: Handling findings with empty physical paths
In `validate_location()`, when `path.strip()` is empty:
- If `logical_location` is also empty, reject with `path-not-in-commit`.
- If `logical_location` is present, evaluate it against `manifest_objects`. With no physical region, admit only when `manifest_objects` is not None and the logical location is in `manifest_objects`. Otherwise reject with `object-not-in-commit`.
- *Rationale*: Fulfills the Copilot added scope from issue 1352.
- *Alternatives considered*:
  - Admitting empty-path findings without checking `manifest_objects`. Rejected because findings without physical code evidence require verified manifest objects as evidence.

## Risks / Trade-offs

- [Risk: Malformed YAML files in reviewed tree cause parsing errors] → Mitigation: `read_manifest_objects()` wraps parsing in exception handling, logging warnings or skipping invalid documents without crashing review admission.
- [Risk: Performance overhead when parsing large manifest sets] → Mitigation: Only scannable YAML manifest files in the reviewed revision are parsed. Parsing uses `yaml.safe_load_all` with fast dictionary access.

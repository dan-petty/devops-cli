# Design

## Decisions

### 1. Shared helper in `repo_content.py`
Use the existing `_REQUIREMENTS_FILES` order and one helper `find_collection_requirements(root: Path) -> Path | None` in `repo_content.py`. The helper returns the first existing path. The collections row, `install_collections`, and the onboard roles row all use this helper.
- **Evidence:** `src/devops_cli/infra/repo_content.py:37` defines `_REQUIREMENTS_FILES = ("collections/requirements.yml", "collections/requirements.yaml")`.
- **Reason:** Reusing the existing two-name discovery removes the drift that caused the defect.

### 2. Pass discovered path to `install_requirements`
Update `install_requirements(tool: AnsibleTool, project: Path, target: Path, requirements: Path | None = None) -> None` in `ansible_facts.py` to accept the resolved requirements file.
- **Evidence:** `src/devops_cli/infra/ansible_facts.py:178` passes `project / REQUIREMENTS_FILE` to `galaxy_argv`.
- **Reason:** Passing the resolved path allows callers to supply the discovered file while preserving backwards compatibility.

## Rejected alternatives

### Accept only `collections/requirements.yml`
- **Evidence:** `src/devops_cli/infra/repo_content.py:37` has supported `.yaml` in onboard since inception.
- **Reason:** Rejecting `.yaml` breaks existing repositories that use `collections/requirements.yaml` and alters the existing `present` check in onboard.

### Repeat the two-name check in each caller
- **Evidence:** `src/devops_cli/infra/plan.py:473` and `src/devops_cli/infra/onboard.py:254` previously drifted from `repo_content.py:200`.
- **Reason:** Duplicated discovery logic causes future drift.

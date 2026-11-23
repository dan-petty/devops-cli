# Proposal: #6698

## Why
The collections row of `devops infra onboard` reads `collections/requirements.yml` or `collections/requirements.yaml`, but `devops infra plan` and `devops infra apply` install only `collections/requirements.yml`. The roles row of onboard also installs only `collections/requirements.yml`. A repo that holds only `collections/requirements.yaml` gets a `present` collections row, but plan and apply run with no pinned collections installed. Closes #6698.

## What Changes
Use one shared discovery rule for the collection requirements file across onboard, plan and apply:
- Export a helper `find_collection_requirements(root: Path) -> Path | None` in `repo_content.py` that checks `_REQUIREMENTS_FILES` (`collections/requirements.yml`, `collections/requirements.yaml`) in order.
- In `plan.py`, `install_collections` uses the discovered requirements file rather than hardcoding `collections/requirements.yml`.
- In `ansible_facts.py`, `install_requirements` accepts an optional `requirements: Path | None = None` parameter, defaulting to `project / REQUIREMENTS_FILE` when omitted.
- In `onboard.py`, `_read_collection_roles` uses the discovered requirements file.
- Add unit tests verifying discovery and installation parity for repositories holding only `collections/requirements.yaml`.

## Capabilities
- `infra-onboard`: The roles row installs collections from `collections/requirements.yaml` when `.yml` is absent.
- `infra-plan`: The plan and apply install step installs collections from `collections/requirements.yaml` when `.yml` is absent.

## Impact
No breaking changes. Repositories with `collections/requirements.yaml` now have their pinned collections correctly installed during onboard, plan, and apply.

## Feasibility
Verified in `src/devops_cli/infra/repo_content.py:37` that `_REQUIREMENTS_FILES` already defines `collections/requirements.yml` and `collections/requirements.yaml`. `read_collection_requirements` uses this tuple, while `plan.py` and `onboard.py` hardcode `REQUIREMENTS_FILE` (`collections/requirements.yml`). Sharing the discovery rule makes behavior consistent across all infra commands.

The change fits one pull request.

## Existing Tool Considered
No open, maintained tool covers repository collection file discovery. The alternatives check in #6698 records `none`. The internal change uses standard Python `pathlib.Path` checks and adds no dependencies, deleting the duplicated hardcoded checks. Tokens to build: ~2,000, keep: 500, elapsed time: < 1 hour.

# Tasks

## 1. Behavior: discover and install collections from requirements.yaml or requirements.yml

- [x] 1.1 Write failing tests: a repository with only `collections/requirements.yaml` gets the same answer from the collections row and from the install of plan; `find_collection_requirements` returns `collections/requirements.yaml` when `.yml` is absent; the onboard roles row installs from `collections/requirements.yaml`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_onboard.py tests/infra/test_plan.py`
- [x] 1.2 Implement `find_collection_requirements` in `repo_content.py`, pass the resolved requirements path to `install_requirements` in `ansible_facts.py`, and update callers in `plan.py` and `onboard.py`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_onboard.py tests/infra/test_plan.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

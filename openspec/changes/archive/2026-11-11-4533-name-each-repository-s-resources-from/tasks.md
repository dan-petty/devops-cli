# Tasks

## 1. Repository reference

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_job.py`, `tests/support/fakes/valkey.py`. Changes: `src/devops_cli/github/repo_ref.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/github/test_repo_ref.py`.

- [x] 1.1 Write the Hypothesis properties and the examples of `RepoRef`, and watch them fail on the missing module
  - Verification: `$ uv run devops ci test tests/github/test_repo_ref.py`
- [x] 1.2 Add `RepoRef`, `ServiceRow`, `service_key` and `CONST_K8S_LABEL_VALUE_RE`, move `is_name_segment` and `is_repository_name` into the module, and change their callers
  - Verification: `$ uv run devops ci test tests/github/test_repo_ref.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/stores/test_roadmap_github_store_repository.py`

## 2. The check of `service.repos`

Kind: behavior. Reads: `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`, `tests/config/test_settings.py`, `tests/roadmap/test_roadmap_inbox_command.py`.

- [x] 2.1 Write the tests that refuse a bad entry and two spellings of one repository, and watch them fail
  - Verification: `$ uv run devops ci test tests/config/test_settings.py`
- [x] 2.2 Refuse a bad entry and a repeated `key` in the settings, and remove the entry check of the inbox command and its message
  - Verification: `$ uv run devops ci test tests/config/test_settings.py tests/roadmap/test_roadmap_inbox_command.py`

## 3. Documents

Kind: documents. Changes: `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`, `src/devops_cli/config/constants.py`.

- [x] 3.1 Add ADR 0022, correct the comment of `CONST_CACHE_NAMESPACE_ROOT`, and generate the documents
  - Verification: `$ uv run devops docs generate --check`

## Workflow follow-up

- #4558 moves `repository_label` and `job_name` into `RepoRef` and puts the labels and the annotation on Jobs and pods.
- #4576 puts `key` on logs, metrics and traces.
- #4566 changes the Argo CD orphan glob for Workflows to `devops-cli-*`.
- #4574 builds the clone path from `RepoRef.path_parts`, and #4603 deletes the data of a removed repository.
- #4527 links the record of the move to ADR 0022, or this record links to it, when the second of the two pull requests merges.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

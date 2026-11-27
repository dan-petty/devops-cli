# Tasks

## 1. Point the default template source at dan-petty/github-workflows

Kind: other

Changes: `src/devops_cli/config/defaults.py`, `docs/CONFIGURATION.md`.

- [x] 1.1 Set `DEFAULT_GITHUB_TEMPLATE_REPOSITORY` to `dan-petty/github-workflows`, and generate `docs/CONFIGURATION.md` again with `uv run devops docs generate`. Manual check: `uv run devops repos onboard dan-petty/github-workflows --plan --only 9` prints the latest release tag of that repository in its heading.
  - Verification: `$ uv run devops ci docs`

## 2. Correct the documents and the decision records

Kind: other

Changes: `docs/repos/onboard.md`, `docs/guidelines/production-readiness.md`, `tests/support/github_repository.py`, `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md`.

- [x] 2.1 Add one dated `Fact out of date` line to the Status History of ADR 0032 and of ADR 0035.
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [x] 2.2 Name dan-petty/github-workflows as the template source in `docs/repos/onboard.md`, `docs/guidelines/production-readiness.md` and the comment of `OPENSPEC_CONFIG` in `tests/support/github_repository.py`. Tell how a repository with another `_src_path` takes the template.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: each repository that infra onboarded takes the template one time from dan-petty/github-workflows with `copier recopy` (dan-petty/infra#217, step 5).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

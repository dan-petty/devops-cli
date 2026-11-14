# Tasks

## 1. Read the repository hooks

Kind: behavior. Reads: `src/devops_cli/github/client.py`, `src/devops_cli/github/session.py`. Changes: `src/devops_cli/github/client.py`.

- [x] 1.1 Add `get_repository_hooks` to the typed client and the `RepositoryHook` model
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 2. Add the webhook row

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/test_roadmap_onboard.py`.

- [x] 2.1 Add `service.webhook_url` and the row 7 states: present, missing, wrong with the fields, and not readable with the login
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes
- [x] 2.2 Add the step text with the URL, the content type, the events and the secret command
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py` passes

## 3. Document the row

Kind: other. Reads: `docs/roadmap/onboard.md`, `docs/CLUSTER.md`. Changes: `docs/roadmap/onboard.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 3.1 Describe row 7 in the onboarding page and hold its events to `docs/CLUSTER.md` step 8
  - Verification: `$ uv run devops ci docs` passes

## 4. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 4.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_onboard.py tests/config` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

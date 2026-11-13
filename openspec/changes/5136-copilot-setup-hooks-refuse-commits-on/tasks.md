# Tasks

## 1. Accept a copilot branch in the branch-name hook pattern

Kind: manifest. Reads: `.pre-commit-config.yaml`, `tests/git/test_branch_form.py`, `src/devops_cli/config/constants.py`, `release-please-config.json`. Changes: `.pre-commit-config.yaml`, `tests/git/test_branch_form.py`.

- [x] 1.1 `test_the_branch_form_of_the_code_is_the_form_of_the_hook` in `tests/git/test_branch_form.py` fails first: it builds the expected pattern from `CONST_BRANCH_TYPES`, `CONST_BRANCH_SLUG_PATTERN` and a module constant `COPILOT_BRANCH_FORM` of `copilot/[a-z0-9]+(?:-[a-z0-9]+)*`, and the hook pattern holds no copilot alternative yet
  - Verification: `$ uv run devops ci test tests/git/test_branch_form.py` fails on the base
- [x] 1.2 Set the `--pattern` argument of the `branch-name` entry to `^(?!(?:(?:feat|fix|perf|refactor|revert|docs|test|build|ci|style|chore)/[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|copilot/[a-z0-9]+(?:-[a-z0-9]+)*)$)`, so the lookahead accepts each name of the two forms and refuses each other name. Set `name: branch name is <type>/<issue>-<slug> or copilot/<slug> (CONTRIBUTING.md, Naming)`. Rewrite the comment above the entry to state both forms and to say that GitHub gives the Copilot cloud agent the `copilot/` branch and the agent cannot rename it. In `tests/git/test_branch_form.py` add the module constant `COPILOT_BRANCH_FORM` and change the expected pattern in `test_the_branch_form_of_the_code_is_the_form_of_the_hook` to `f"^(?!(?:{form}|{COPILOT_BRANCH_FORM})$)"`
  - Verification: `$ uv run devops ci test tests/git/test_branch_form.py` passes

## 2. Extend the naming-form and setup-step tests with the copilot names

Kind: other. Reads: `tests/invariants/test_workflow_contracts.py`, `.pre-commit-config.yaml`, `.github/workflows/copilot-setup-steps.yml`. Changes: `tests/invariants/test_workflow_contracts.py`.

- [x] 2.1 In `test_a_commit_on_a_branch_that_breaks_the_naming_form_is_refused`, add `copilot/fix-login-bug`, `copilot/sub-pr-12` and `copilot/fix-4773` to `accepted`, and add `copilot/`, `copilot/Fix-login`, `copilot/fix_login` and `Copilot/fix-login` to `refused`. In `test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs`, add the assertion that the step named `Install the git hooks` holds the run `uv run pre-commit install --install-hooks`, so the setup steps keep the hook installation
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py` passes

## 3. State both accepted branch forms in the Naming table

Kind: other. Reads: `CONTRIBUTING.md`, `.pre-commit-config.yaml`. Changes: `CONTRIBUTING.md`.

- [ ] 3.1 Rewrite the Branch row of the Naming table so it gives both accepted forms: `<type>/<issue>-<slug>` for a person and for the implement job, and `copilot/<slug>` for the branch that GitHub gives the Copilot cloud agent and that the agent cannot rename. Keep the `no-commit-to-branch` hook as the check and keep the sentence about `devops repos worktrees add`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `CONTRIBUTING.md` section 5 so the Branch row of the Naming table names both accepted branch forms and the hook that refuses each other name
  - Verification: `$ uv run devops ci docs` passes

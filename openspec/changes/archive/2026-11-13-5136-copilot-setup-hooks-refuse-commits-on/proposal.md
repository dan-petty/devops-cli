# Proposal

## Why

The Copilot setup steps install the `branch-name` hook, and that hook refuses each commit on a branch outside `<type>/<issue>-<slug>`. The Copilot cloud agent works on a `copilot/` branch that it cannot rename, so the hook stops the agent at its first commit with an unknown Git error (#5136).

## What Changes

- The `--pattern` of the `branch-name` hook accepts `copilot/<slug>` beside `<type>/<issue>-<slug>`, so a commit on the branch of the Copilot cloud agent passes and each other name is still refused.
- The `name` of the `branch-name` hook and the comment above it state both accepted branch forms.
- `tests/git/test_branch_form.py` builds the expected pattern from `CONST_BRANCH_TYPES`, `CONST_BRANCH_SLUG_PATTERN` and a module constant for the copilot form, so the code and the hook stay in one form.
- `test_a_commit_on_a_branch_that_breaks_the_naming_form_is_refused` in `tests/invariants/test_workflow_contracts.py` gains the three copilot names as accepted and four names outside both forms as refused.
- `test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs` gains the assertion that the step named `Install the git hooks` holds `uv run pre-commit install --install-hooks`, so the setup steps keep the hook installation.
- `CONTRIBUTING.md` states both accepted branch forms in the Branch row of its Naming table.
- The change carries a spec delta for the new capability `branch-name-hook`, because `.pre-commit-config.yaml` and `CONTRIBUTING.md` are outside the paths that skip a delta.
- No requirement is added for the install step, because the existing requirement `Remote agent sessions install the git hooks` of `devcontainer-agent-config` already says that the Copilot setup steps install the hooks.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `branch-name-hook`: The branch-name hook accepts a copilot branch, The branch-name rule keeps its refusal for other names, The hook states both accepted branch forms

### Modified Capabilities

None.

## Impact

- Code: `.pre-commit-config.yaml`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/git/test_branch_form.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

- The premise is confirmed by the probe lines, word for word: "The path `.github/workflows/copilot-setup-steps.yml` is a file of the staging commit." and "The path `.pre-commit-config.yaml` is a file of the staging commit."
- `read_file` of `.pre-commit-config.yaml` lines 1-25 showed `.pre-commit-config.yaml:1:default_install_hook_types: [pre-commit, pre-push]`, the entry at `.pre-commit-config.yaml:16:name: branch name is <type>/<issue>-<slug>` and its pattern at `.pre-commit-config.yaml:19:- '^(?!(?:feat|fix`.
- The pattern is a negative lookahead, so `no-commit-to-branch` fails when the pattern matches the branch name. `copilot/fix-login-bug`, `copilot/sub-pr-12` and `copilot/fix-4773` are outside `<type>/<issue>-<slug>`, so the lookahead succeeds and the hook refuses each of them; the reproduction steps of the issue give the same three results. The pattern starts with `^`, so `re.search` and `re.match` judge the same position.
- `read_file` of `tests/git/test_branch_form.py` showed that the hook pattern is compared with the code form at `tests/git/test_branch_form.py:48:assert _branch_name_hook_pattern() == f"^(?!{form}$)"`, so that equality test changes in the same group as the pattern.
- `read_file` of `tests/invariants/test_workflow_contracts.py` showed the existing census of branch names at `tests/invariants/test_workflow_contracts.py:831:def test_a_commit_on_a_branch_that_breaks_the_naming_form_is_refused`, with its count of the 11 types at `tests/invariants/test_workflow_contracts.py:858:) == (11, [], [])`; the change adds the copilot names to its `accepted` and `refused` lists and adds no second test of the same rule.
- `read_file` of `tests/invariants/test_workflow_contracts.py` showed the existing assertion of the setup steps at `tests/invariants/test_workflow_contracts.py:1385:def test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs`, whose script list holds `tests/invariants/test_workflow_contracts.py:1420:"uv run pre-commit install --install-hooks",`; the change extends that test with the step name and adds no second test.
- `read_file` of `src/devops_cli/config/constants.py` lines 735-775 showed the staged values: `CONST_BRANCH_TYPES` is the 11 types `feat`, `fix`, `perf`, `refactor`, `revert`, `docs`, `test`, `build`, `ci`, `style` and `chore` at `src/devops_cli/config/constants.py:754:CONST_BRANCH_TYPES: Final[tuple[str, ...]] = (`, and `CONST_BRANCH_SLUG_PATTERN` is `[a-z0-9]+(?:-[a-z0-9]+)*` at `src/devops_cli/config/constants.py:767:CONST_BRANCH_SLUG_PATTERN: Final[str] = "[a-z0-9]+(?:-[a-z0-9]+)*"`.
- `read_file` of `src/devops_cli/commands/ci.py` lines 860-900 showed the `docs` row at `src/devops_cli/commands/ci.py:881:name="docs",`, whose command is `uv run devops docs check`.
- `read_file` of `CONTRIBUTING.md` lines 190-202 showed the Branch row at `CONTRIBUTING.md:196:| Branch | `<type>/<issue>-<slug>` |`, which names one accepted form and would contradict the hook after the merge.
- `read_spec` of `devcontainer-agent-config` returned the requirement `Remote agent sessions install the git hooks`, whose text holds the sentence "The Copilot setup steps SHALL install the hooks." That existing requirement already covers the install step, so the plan adds no requirement that repeats it.
- `read_file` of `src/devops_cli/git/branch_form.py` lines 50-71 showed `src/devops_cli/git/branch_form.py:64:match = _BRANCH.fullmatch(branch)`, which reads the issue out of a branch; a copilot branch names no issue, so the plan leaves that code unchanged.
- `find_issues` with the terms `copilot setup hooks` returned `#5147 open test(ci): prove the Copilot setup hooks in a live Copilot run`, the follow-up that holds the live run.
- The live Copilot run is not checked by this run: only GitHub starts that run and no tool here observes it, so #5147 holds it. The `pre-push` hook `branch-current` is not checked either: the agent cannot rebase, and #5147 records a push that the hook refuses.
- The plan answers the review findings: the duplicate requirement goes away because the existing requirement already states that the setup steps install the hooks; group 1 and group 2 extend the two tests that exist instead of adding copies; and the citations now point at the staged lines of the constants, of the `docs` row and of the Naming table.
- `_branch_name_hook_pattern` reads `.pre-commit-config.yaml` under `REPO_ROOT`, so its precondition is a checkout of the repository.
- The verify `uv run devops ci test tests/git/test_branch_form.py` runs the programs `uv`, `devops`, `python` and `pytest`, each from the runner image; its failure class is `test`, action `repair`, and it needs no network. The pod runs it with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault`.
- The verify `uv run devops ci docs` runs the `docs` row, whose programs `uv`, `devops` and `python` are in the runner image; its failure class is `lint`, action `repair`.
- First checks against the real system, each with its command: `uv run devops ci test tests/git/test_branch_form.py`, then `uv run devops ci test tests/invariants/test_workflow_contracts.py`, then `uv run devops ci docs`.

## Existing Tool Considered

The `no-commit-to-branch` hook of pre-commit/pre-commit-hooks v6.0.0, pinned at `rev: v6.0.0` in `.pre-commit-config.yaml`, covers the need through its `--pattern` argument; the change extends that one pattern and builds no code.

## Dependencies

None.

# Design

## Decisions

- **Extend the one `--pattern` of the `branch-name` hook with the alternative `copilot/[a-z0-9]+(?:-[a-z0-9]+)*`.**: `--pattern` is the only branch filter that the hook gives, so the rule stays in one place, and the `^` anchor makes the negative lookahead judge the whole name.
- **Keep the `Install the git hooks` step in the Copilot setup steps.**: The owner rule of 2026-10-20 in the issue scopes the trigger and builds no escape, and the step keeps the other hooks on each commit and push of the agent.
- **Update `test_the_branch_form_of_the_code_is_the_form_of_the_hook` in the same group as the pattern, building the expected pattern from `CONST_BRANCH_TYPES`, `CONST_BRANCH_SLUG_PATTERN` and a module constant for the copilot form.**: The branch form of the code does not change, and the test still fails when the types, the slug pattern and the hook drift apart.
- **Extend `test_a_commit_on_a_branch_that_breaks_the_naming_form_is_refused` instead of adding a second test of the same rule.**: That test is the census of the accepted and refused branch names and already holds the count of the 11 types, so a second test would copy its lists.
- **Extend `test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs` with the step name instead of adding a test of the workflow.**: That test already asserts the install command in the script list of the workflow, so the step name belongs in its assertion.
- **Add no requirement for the install step.**: The requirement `Remote agent sessions install the git hooks` of `devcontainer-agent-config` already holds the sentence that the Copilot setup steps install the hooks, and a second requirement would repeat it.
- **Write the copilot form in the hook and in the test, and not in `src/devops_cli/config/constants.py`.**: No module of `src/` reads the form, and the Naming rule of `CONTRIBUTING.md` puts a constant in `config/constants.py` only when modules of two or more packages import it.
- **Leave `parse_branch` and `devops repos worktrees add` unchanged.**: A copilot branch names no issue, so `src/devops_cli/git/branch_form.py:64:match = _BRANCH.fullmatch(branch)` keeps returning nothing for it and no item is claimed by mistake.
- **State both accepted forms in the Branch row of the Naming table of `CONTRIBUTING.md`.**: The hook name cites that section, and a table that names one form would contradict the hook after the merge.
- **Defer the live Copilot run to #5147.**: Only GitHub starts that run and this job cannot observe it, while the two tests prove the pattern on each sample name.

## Rejected alternatives

- **Remove the `Install the git hooks` step from the Copilot setup steps.**: The issue records the owner rule of 2026-10-20: scope the trigger and build no escape. The comment above the step in `.github/workflows/copilot-setup-steps.yml` also says that the step builds the environments of the hook repositories.
- **Set `SKIP=branch-name` in the Copilot setup steps.**: An environment variable that turns the hook off is an escape, and it hides the hook from each later commit of the agent.
- **Add a second `no-commit-to-branch` entry with `--branch`.**: `--branch` refuses one exact name and cannot express the `copilot/` prefix, so the rule would sit in two places.
- **Install only the `pre-push` hook type in the Copilot setup steps.**: That drops each `pre-commit` hook from the commits of the agent, so the agent commits with no check at all.
- **Make `parse_branch` accept a copilot branch.**: `src/devops_cli/git/branch_form.py:64:match = _BRANCH.fullmatch(branch)` reads the issue out of a branch, and a copilot branch names no issue, so `devops repos worktrees add` would claim a wrong item.
- **Add a new test module under `tests/git/` for the copilot names.**: `tests/git/test_branch_form.py` already holds the equality of the hook pattern and the code form, and `tests/invariants/test_workflow_contracts.py` already holds the accepted and refused lists, so a new module would copy both.

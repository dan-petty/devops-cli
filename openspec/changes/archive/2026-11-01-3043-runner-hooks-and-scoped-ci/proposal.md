# Proposal

## Why

Issue #3043 (tracker #3027): a person who works in the devcontainer runs the hooks of `.pre-commit-config.yaml` at each commit and at each push. The runner Job runs fewer checks. Its step runs `ruff`, `mypy --strict` on the changed files and the verification commands of the group, then commits. The Job runs no hook. Then it pushes and waits for the CI of the pull request. A defect that the project's own checks find in seconds (an ast-grep rule, the OpenSpec gate, a docs drift, a test of the changed code) first shows on the pull request. Each such defect costs one push, one CI run and one fix step, and a second failure stops the item.

The owner asks (2026-11-01) that the runner applies the standards, the workflow and the checks of the devcontainer. The rule for the four issues of this wave: the runner runs the same checks from the same definitions, and a test fails when the two drift.

## What Changes

- A new module `src/devops_cli/roadmap/implement_hooks.py` runs the hooks of the repository with `pre-commit run --hook-stage <stage>` as a child of the Job, with no GitHub token. It also installs the hook environments with `pre-commit install-hooks`, into `PRE_COMMIT_HOME` on the home volume of the Job.
- The Job installs the hook environments once, before the first step. A failed install stops the item before any model request.
- Each step runs the `pre-commit` stage on the staged changes as its last exit check. The hooks are those of `.pre-commit-config.yaml`: the branch-name and `main` guards, the file hygiene hooks, `detect-private-key`, `ruff-check`, `ruff-format`, the ast-grep scan and test, and the OpenSpec gate. A hook that fixes a file is staged again and the hooks run once more, as a person does with `git add` and a second commit. A hook that still fails goes to the agent as a repair turn.
- The one extra turn of a step becomes a number of repair rounds. The new setting `roadmap.implement.repair_rounds` (default 3, variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_REPAIR_ROUNDS`) bounds the extra turns for a failed `ruff`, a failed `mypy`, a failed hook and a missing tick. Only an exhausted budget stops the step. `StepOutcome.repair_rounds` counts the rounds used, and the comment of the Job on the pull request shows the count for each group.
- A new module `src/devops_cli/roadmap/implement_scoped_ci.py` defines the scoped checks and runs them. After the last group, the docs and the archive, and after the final rebase, the Job runs: the `pre-push` stage of the hooks over the commits of the item; `devops ci --check --only constructs,docs,openspec`; and `devops ci test` with the changed Python files of `src/` and `tests/`, which selects the tests of the changed code. A failed check goes to a fix step with its log, up to `repair_rounds` times. The Job pushes only a head that passed all of them. An exhausted budget stops the item and pushes nothing. The comment on the pull request lists each scoped check with its time.
- The `pre-push` hook `devops-ci-pre-push` runs `lint` and `format`. A new hook `devops-ci-workflows-pre-push` runs `actionlint` and `zizmor` only when a push changes `.github/workflows/` or `.github/actions/`. The runner image holds no `actionlint`, and a check that does not apply to a push is not run (the rule of the owner, 2026-10-20). A person in the devcontainer no longer waits for these two checks on a push that changes no workflow.
- The prompt of the step tells the agent that the hooks run on its changed files and that a failure gives it a turn. `k8s/README.md` step 16 and `docs/ROADMAP_WORKFLOW.md` describe the hooks, the scoped checks and the setting.
- Tests guard the drift: each scoped row is a row of `devops ci`; each local hook runs a program that the runner image holds; the branch-name hook accepts every branch type that the job makes. A replay test with a stub model shows an ast-grep violation repaired before the push, and a hook failure that the agent cannot fix, which uses all rounds and stops with the hook output.
- Observable behavior changes (a setting, a stop reason, a comment line and a table row), so the change carries spec deltas.
- The change fits one pull request.

The change does not install the git hooks (`pre-commit install`) in the clone of the Job, and it does not add `actionlint` or any other tool to the image. See the design.

The post-push fix of a failed check stays as it is: #3053 owns repair rounds after the push.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the hooks are an exit check; the extra turn becomes `repair_rounds` rounds; the outcome counts the rounds.
- `roadmap-implement-job`: the Job installs the hook environments, runs the scoped checks before the push, and shows them in its comment.
- `roadmap-implement-runner`: the local hooks run only programs that the image holds.

## Impact

- Code: `src/devops_cli/roadmap/implement_hooks.py` (new), `src/devops_cli/roadmap/implement_scoped_ci.py` (new), `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Hook configuration: `.pre-commit-config.yaml`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Documents: `k8s/README.md` (step 16), `docs/ROADMAP_WORKFLOW.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` (generated), `openspec/specs/roadmap-implement-step/spec.md`, `openspec/specs/roadmap-implement-job/spec.md` and `openspec/specs/roadmap-implement-runner/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_implement_hooks.py` (new), `tests/roadmap/test_roadmap_implement_scoped_ci.py` (new), `tests/roadmap/test_roadmap_implement_step_hooks.py` (new), `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_ticks.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_prompt.py`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_runner_hooks.py` (new).
- Run time: one `pre-commit` stage run per step commit (about 10 s on a host with 4 CPUs, measured), one environment install per Job (9 s and 51 MB, measured), and the scoped checks once after the last group (see Feasibility).

## Feasibility

- The runner installs no hook. `git grep -n "pre-commit" Dockerfile` prints nothing. The `runner` stage of `Dockerfile` runs `uv sync --locked --no-editable` with the dev group, and `pyproject.toml` lists `pre-commit==4.6.2` and `ast-grep-cli==0.51.0` in that group. So `uv run pre-commit` and `uv run ast-grep` work in the Job. `_commit` of `implement_step.py` runs `git commit` in a clone with no hook, so no hook runs today.
- `.pre-commit-config.yaml` holds two remote repositories (`pre-commit/pre-commit-hooks` v5.0.0 and `astral-sh/ruff-pre-commit` v0.16.8) and four `language: system` hooks. The system hooks run `uv run ast-grep ...` and `uv run devops ci --only ...`, and the image holds `uv`, `ast-grep` and `openspec`. Only the two remote repositories need a fetch. With an empty `PRE_COMMIT_HOME`, `uv run pre-commit install-hooks` (pre-commit 4.6.2, Python 3.14) cloned both and built both environments in 9 s of wall time and 51 MB, and `pre-commit run --hook-stage pre-commit --all-files` then passed in 29 s.
- The Job can fetch them. `k8s/devops/networkpolicy.yaml`, rule 4 of `devops-default-perimeter`, admits TCP 443 to every public address. The root filesystem of the Job is read-only, `HOME` is `/home/devops` on the `home` emptyDir (4 Gi), and `DEVOPS_CLI_DATA_DIR` is `/home/devops/.data`. So `PRE_COMMIT_HOME` under the data directory is writable.
- The premise "install the git hooks" fails on one point. `_pin_github_token` of `core/process.py` gives `GH_TOKEN` to every `git` child, and `git commit` and `git push` run a hook as a child of git. The agent can edit `.pre-commit-config.yaml`. A hook that the agent wrote would run with the GitHub token of the session in its environment, and the pod can reach the public network. The Job already keeps every other child of the agent's code (`uv`, `ruff`, `pytest`) without the token, because `build_subprocess_env` drops names that match `*TOKEN*`. So the Job runs the hook stages itself with `pre-commit run`, a child that is no `git` or `gh` client, and installs no git hook. The commit and the push stay free of hooks. This keeps the intent (the same hooks, at the same two moments, with a repair chance) and removes the exposure.
- A hook failure that happens in `git push` would come after the last repair chance. Running the `pre-push` stage before the push gives the agent a repair round for it.
- `pre-commit` exits 1 when a hook fails or changes a file, and 3 for an unexpected error (`error_handler.py` of pre-commit 4.6.2). So exit 1 is a repairable failure, and any other non-zero code stops the step with the output.
- `devops ci test` takes source and test files and selects the covering tests (`devops ci test --help`). `devops ci --check --only constructs,docs,openspec` ran in 24 s (3.4 s for ast-grep, 11 s for docs, 23 s for OpenSpec, concurrent). The `pre-push` stage ran in 9 s. The extra run time of an item with three groups is about 3 commits x 10 s of hooks, 9 s of environment install, 9 s of the `pre-push` stage, 24 s of static rows, and the tests of the changed code. In the devcontainer, `devops ci test` for the tests of one changed module takes between 10 s and 90 s. So an item runs about 2 to 3 minutes longer, in a Job that runs about one to two hours. CI time is not affected.
- The branches of the Job have the form `<type>/<issue>-<slug>` (`branch_form.branch_name`), the form that the `branch-name` hook accepts. A test holds this against the pattern in `.pre-commit-config.yaml`.

## Existing Tool Considered

`pre-commit` 4.6.2 (already in the lockfile) runs the hooks, reads the single definition in `.pre-commit-config.yaml` and installs the environments. `devops ci` (the table `get_check_specs`) runs the scoped rows and `devops ci test` selects the tests of the changed files. `git diff --name-only` lists the changed files. The change builds only the glue: two modules of about 120 lines each that start these tools, read their exit codes and give their output to the agent. The written cost: about 90 000 tokens to build, 5 000 tokens a year to keep, and 15 000 tokens to fix until it matches the tools; about one working day. The change replaces the single extra turn of `implement_step.py` with a loop and deletes no other code. No tool runs a coding agent through a repair loop with the hooks of a project.

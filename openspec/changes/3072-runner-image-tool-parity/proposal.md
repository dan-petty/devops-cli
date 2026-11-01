# Proposal

## Why

#3072 (tracker #3027): the owner asks that the runner Job use the standards, workflow and checks of the devcontainer. The runner image lacks tools that the gate and the hooks need. A check that needs one of them fails in the Job, or a test that needs one skips there, and the same change fails on the pull request later. The shell of a step also refuses `grep`, `cat`, `ls`, `head`, `tail` and `find`, which only read. On 2026-11-01, shell refusals ended 3 of 13 stops (#2572, #2554, #2396). The shell policy lives in three places: a tuple of programs, a table of replacements, and a copy of both in the prompt.

## What Changes

- A table `RUNNER_TOOLS` in `src/devops_cli/roadmap/runner_tools.py` lists each program that the runner image holds, its source, why it is there, and its version command. A second table `NOT_IN_RUNNER` names each program that the image does not hold, with the reason.
- The `runner` stage of `Dockerfile` adds `shellcheck`, `curl` and `jq` (apt), `actionlint` (the digest of the devcontainer), and Trivy and promtool (`devops install-tools`, the pins of `tools.lock`). Its last step runs `python -m devops_cli.roadmap.runner_tools`, so a missing tool or a wrong version fails the build.
- The smoke test of `ci.yml` and `release.yml` drops its list of `--version` lines for single tools. It runs the same check module on the loaded image and fails when the image is larger than 3000000000 bytes.
- Tests fail when a program of a `devops ci` row, a hook, a required job of `ci.yml`, a live-marked test or `tools.lock` is in neither table, and when a pin of the table differs from a Dockerfile.
- The shell policy becomes one table in `src/devops_cli/roadmap/implement_shell_policy.py`: each program with its access class (`read`, `write` or `network`), its refused arguments, and the programs that are refused with what to do instead. The allowlist of the shell, the refusal hint, the prompt and `docs/ROADMAP_WORKFLOW.md` read it. The shell now allows `grep`, `cat`, `ls`, `head`, `tail` and `find` without `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint`, `-fprint0`, `-fprintf` and `-fls`.
- The change has spec deltas: the runner stage, the table, the smoke test, and the shell tool are observable behavior of the image and of the step.
- The change fits one pull request. It touches `implement_step.py` and the prompt in one line each (the table fills the prompt), so the parallel changes of this wave (#3043, #3090, #3097) merge with small conflicts at most.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: the runner stage holds more tools, the table, the smoke test.
- `roadmap-implement-step`: the shell tool admits the programs of one table, with refused arguments.

## Acceptance

- Criterion 1 (the image build fails if a tool is missing or runs the wrong version): group 2. The build runs the check of group 1 as its last step.
- Criterion 2 (the prompt, the guard and the documents read the same table): group 3.
- Criterion 3 (the image size and the pull time are stated, and the size grows by no more than a stated bound): group 2 measures them; group 4 states them in `k8s/README.md`. The smoke test fails above 3000000000 bytes.
- Criterion 4 (hermetic tests do not depend on the tools of the host): the new tests read files and use `process_fake`. They start no program.
- Criterion 5 (a tool that the table forbids gives a refusal text with the allowed way): group 3.

## Existing Code

- `Dockerfile`, stage `runner`: it holds `git`, the dev group of `uv.lock` (pytest, ruff, mypy, bandit, deptry, ast-grep, zizmor, pre-commit) and the OpenSpec of `tools.lock`. It lacks actionlint, shellcheck, Trivy, promtool, curl and jq (`docker run` on the image built from `origin/main` prints MISSING for each).
- `src/devops_cli/tools_lock/tools.lock` and `devops install-tools`: the pinned installer that the builder stage uses for OpenSpec. The runner stage reuses it for Trivy and promtool.
- `.devcontainer/Dockerfile`: the actionlint image digest, which `ci.yml` also uses. The existing test `test_actionlint_digest_pinned_in_dockerfile_and_ci` keeps these two equal. The runner stage uses a third copy of the digest, and the new test compares it with the devcontainer.
- `get_check_specs()` in `src/devops_cli/commands/ci.py`: the rows of `devops ci` as data. The new test reads the argv of each row, so a row that starts a new program fails the test.
- `src/devops_cli/config/commands.py`: `IMPLEMENT_SHELL_PROGRAMS`, `IMPLEMENT_ALLOWED_PROGRAMS` and `IMPLEMENT_SHELL_REPLACEMENTS`. The change moves them into the table module and derives them from it.
- `src/devops_cli/roadmap/implement_shell_refusal.py`: the hook that adds the hint to a refusal. It also refuses a refused argument now.

## Impact

- Image: the runner image grows (measured in group 2, stated in `k8s/README.md`). The `service` image does not change.
- Code: `src/devops_cli/roadmap/` (two new modules, three edited), `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, the prompt `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Tests: `tests/roadmap/`, `tests/invariants/test_runner_image.py`.
- Documents: `k8s/README.md` (Runner Jobs), `docs/ROADMAP_WORKFLOW.md`.
- Workflows: `ci.yml` and `release.yml` (the smoke test of the runner image).
- Deleted: the `--version` lines for single tools in the two smoke tests, the three constants in `config/commands.py` (they move), the hand-written program list and table in the prompt, and the tests that expect `grep`, `cat`, `ls`, `head`, `tail` and `find` to be refused (they test other refused programs now).

## Feasibility

Checked on `origin/main` (ae2d8e1f) on 2026-11-01.

- The runner image lacks the tools. `docker build --target runner` of `origin/main` gives an image where `command -v` prints MISSING for `actionlint`, `shellcheck`, `trivy`, `promtool`, `jq` and `curl`, and finds `pre-commit`, `ast-grep`, `zizmor`, `bandit`, `deptry`, `git` and `openspec`. The dev group of `uv.lock` already holds pre-commit, ast-grep, zizmor, bandit and deptry, so the premise "install pre-commit" needs no new install.
- The need comes from the code, not from a guess. The programs of `get_check_specs()` are `uv`, `npm`, `actionlint`, `nice` and the tools that `uv run` starts. The hooks of `.pre-commit-config.yaml` run `pre-commit`, `uv run ast-grep` and `uv run devops`. The `static` and `test` jobs of `ci.yml` install OpenSpec, Trivy, actionlint and promtool. `@pytest.mark.live(...)` names `jq`, `curl`, `zsh`, `bash` and others. The tests in group 1 read these sources and fail on a program that is in neither table.
- The premise "kube-linter, popeye and the other scanners are probably needed" fails. The `static` job installs no scanner, so the gate reports them as not run. With popeye on PATH the test `test_the_direct_executor_refuses_a_network_profile_before_it_starts_the_tool` fails with "host path reached without a fake" (`uv run devops ci test tests/ai/test_tool_executor_contract.py`, #2165). A runner with popeye would fail a test that the gate passes. So the table leaves the scanners out, with the reason.
- The tools that the issue calls not needed (kubectl, helm, minikube, docker, bubblewrap, socat) are left out: no row, hook, job step or non-opt-in test runs them, and the Job mounts no cluster token (`k8s/README.md`, Runner Jobs). zsh is left out: the `Ubuntu2404` image of the GitHub runner has no zsh (runner-images README), so its tests skip in the gate too. curl and jq are in that README, so they join the image. npm stays out: the image deletes it on purpose (`roadmap-implement-runner` spec), so the `audit` row is the one row whose `npm audit` cannot run in the Job.
- The build works. `docker build --target runner .` with the change succeeded; the last step printed `All 31 runner tools run at their pins.` in 7 s. With `PATH` cut to `/app/.venv/bin:/opt/devops-tools/bin:/usr/local/bin` the same module exits 1 and names `git`, `shellcheck`, `curl`, `jq` and the other missing tools. `actionlint` ran in the image on the workflows of the checkout and exited 0, with shellcheck found.
- The shell guard takes only the first word: the harness `Shell` reads `allowed_commands` for the first token and `denied_operators` as substrings (`pydantic_ai_harness/shell/_toolset.py`, `_check_command`). So a refused argument needs a check of our own in the hook that already adds the refusal hint.
- Live evidence for the shell: the comment on #3072 lists 3 of 13 stops on shell refusals, `grep` 6 times on #2554.

## Existing Tool Considered

- `devops install-tools` and `tools.lock` already install a pinned tool with a checksum. The change reuses them for Trivy and promtool, and adds no download.
- The actionlint image of the devcontainer is reused by digest, and apt gives shellcheck, curl and jq. No new pinned download is added.
- `pre-commit` is a dev dependency of the lockfile; no install is added.
- `hadolint` could lint the Dockerfile, but it is not installed here and the project does not use it. The CI job `Runner Image` builds the file.
- For the shell guard, the harness `Shell` supports no argument rules (`_check_command`), so the change adds a small check to the existing hook. No open library covers "refuse these arguments of one program" for this harness. The written cost: about 40 lines of code and 10 tests, written in this change; keeping it costs one table row for each new refused argument.

# Tasks

## 1. The table of runner tools

Kind: behavior. Reads: `src/devops_cli/commands/ci.py` (`get_check_specs`), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `src/devops_cli/tools_lock/`. Changes: `src/devops_cli/roadmap/runner_tools.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_runner_tools.py`.

- [x] 1.1 Write the failing tests in `tests/roadmap/test_roadmap_runner_tools.py`: each program of a `devops ci` row, of a hook, of a required job of `ci.yml`, of a live-marked test and of `tools.lock` is in `RUNNER_TOOLS` or `NOT_IN_RUNNER`; a tool that fails the image scan is left out with the reason; the pins agree with the Dockerfiles; the check of one tool passes, fails on a version, on an exit status and on a missing program. Verification: `uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` fails because the module does not exist
- [x] 1.2 Write `src/devops_cli/roadmap/runner_tools.py` with the two tables, the check and `main`, and the messages in `messages.py`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` passes the tests that read no Dockerfile
- [x] 1.3 Verify the types and the style. Verification: `uv run mypy --strict src/devops_cli/roadmap/runner_tools.py` and `uv run ruff check src tests`

## 2. The runner image and its smoke test

Kind: image and workflow change (no test of its own; the tests of group 1 read the files). Changes: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/invariants/test_runner_image.py`.

- [x] 2.1 Add the apt packages `curl` and `jq`, the install of promtool, and the last smoke step to the `runner` stage of `Dockerfile`, and move promtool to 3.15.1 in `tools.lock`. Verification: `docker build --target runner -t devops-cli-runner:local .` exits 0 and prints "All 28 runner tools run at their pins."
- [x] 2.2 Verify that a missing tool fails the check. Verification: `docker run --rm -e PATH=/app/.venv/bin:/usr/local/bin --entrypoint python devops-cli-runner:local -m devops_cli.roadmap.runner_tools` exits 1 and names `curl`
- [x] 2.3 Replace the `--version` lines in the smoke test of `ci.yml` and `release.yml` with the check module and the size bound, and change the invariant test to match. Verification: `uv run devops ci test tests/invariants/test_runner_image.py tests/roadmap/test_roadmap_runner_tools.py` and `uv run devops ci actionlint`
- [x] 2.4 Measure the size and the pull cost of the image, and run `actionlint` in it. Verification: `docker image inspect devops-cli-runner:local --format '{{.Size}}'` is under 3000000000 (2510467245 measured)
- [x] 2.5 Run hadolint if it is installed. Verification: `command -v hadolint` prints nothing here, so the CI job `Runner Image` is the lint of the file

- [x] 2.6 Scan the image as the job of `ci.yml` does, and keep out each tool that fails. Verification: `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --ignorefile .trivyignore devops-cli-runner:local` exits 0. The first build failed it for `actionlint`, Trivy and promtool 3.15.0, so `actionlint`, `shellcheck` and Trivy are in `NOT_IN_RUNNER` (issue #3108 tracks their return) and promtool is at 3.15.1

## 3. The shell policy table

Kind: behavior. Reads: `src/devops_cli/config/commands.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_step.py`, the prompt. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/`.

- [x] 3.1 Write the failing tests: the read-only programs run; `find -exec` and the other refused arguments give a refusal with the way to go, counted as refused; the allowlist, the refusal hint, the prompt and the table agree. Update the tests that expect `cat`, `ls`, `grep`, `head`, `tail` or `find` to be refused. Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_implement_shell_refusal.py` fails for the right reason
- [x] 3.2 Write `implement_shell_policy.py` with `SHELL_PROGRAMS`, `SHELL_REFUSALS`, the derived constants and the rendering of the two tables. Remove the three constants from `config/commands.py` and update their imports. Verification: `! git grep -n "IMPLEMENT_SHELL_REPLACEMENTS" -- src/devops_cli/config` and `uv run mypy --strict src/devops_cli/roadmap`
- [x] 3.3 Refuse a refused argument in the hook, and fill the prompt from the table with two placeholders. Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_implement_shell_refusal.py tests/roadmap/test_roadmap_implement_prompt.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_tool_log.py`
- [x] 3.4 Refuse a redirect to a file for a program with access `read`, and a word with `$` for `find`. Write the failing tests first: `grep -rn x src > out.txt`, `cat a >> b`, `ls > f`, `find . -ex${U}ec ...`, `find . -fpr${U}int ...`, `find . -del$IFS`; `2>&1` and `>/dev/null` pass. Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py` fails before the change and passes after it

## 4. Documents

Kind: documents. Changes: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, and the generated documents.

- [x] 4.1 Update the Image bullet of Runner Jobs in `k8s/README.md` with the tools, the table, the smoke test, and the measured size, size bound and pull cost. Verification: `uv run devops ci docs`
- [x] 4.2 Add the rendered shell tables to `docs/ROADMAP_WORKFLOW.md`, and test that they equal the table. Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py`
- [x] 4.3 Regenerate the documents. Verification: `uv run devops docs generate --sync-readme` then `uv run devops ci docs`

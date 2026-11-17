# Proposal

## Why

The review command cannot run in the runner shell (#3827): its default executor starts scanners in a `bubblewrap` sandbox, and the pod's `RuntimeDefault` seccomp profile refuses the `unshare` that the sandbox needs. The runner image also holds none of the review scanners that `NOT_IN_RUNNER` names, so a review in the runner finds nothing, and a scanner that is not installed reads as no finding. The change runs the review in the runner pod, adds the scanners to the image, and fails the review closed when one is missing.

## What Changes

- Add `review_tool_executor` to `src/devops_cli/security/tool_executor.py`: it answers the direct executor in the pod of a runner Job, else the sandbox executor.
- Thread `in_runner` through `execute_review_workflow` in `src/devops_cli/ai/review/runner.py`, and pass the setting `roadmap.implement.in_runner` at each of the five calls in `src/devops_cli/commands/review.py`.
- Raise `ReviewScannerMissingError` from `src/devops_cli/exceptions/ai.py` when a review in the runner pod finds an analyzer that its files need and the image lacks: the report lists that scanner as not installed and the command exits 1.
- Move Gitleaks 8.30.1, Pluto 5.24.4, osv-scanner 2.6.0, golangci-lint 1.64.8 and Semgrep 1.179.0 from `NOT_IN_RUNNER` to `RUNNER_TOOLS` in `src/devops_cli/roadmap/runner_tools.py`, and install each in the `runner-tools` stage of `Dockerfile`.
- Keep `kubectl` and `kube-linter` out of the image: #3562 and its split #5394 own them, and #3108 already returned actionlint, shellcheck and Trivy.
- Regenerate `docs/ERRORS.md` for the new error class, and name the added scanners and the image scan in `docs/CLUSTER.md`.
- Record the executor choice in `docs/adr/0028-review-scanners-run-in-the-runner-pod.md`, and regenerate the ADR index in `docs/adr/README.md` with `uv run devops docs generate`, so the table holds the row of the new record.
- The change carries a spec delta: the review executor, the fail-closed rule and the runner image tool set are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-sandbox`: A review in the runner pod fails closed when a scanner is missing, A review runs its tools in the sandbox, or directly in the runner pod
- `roadmap-implement-runner`: The runner image holds the scanners of a review

## Impact

- Code: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/exceptions/ai.py`, `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`
- Documents: `docs/ERRORS.md`, `docs/CLUSTER.md`, `docs/adr/0028-review-scanners-run-in-the-runner-pod.md`, `docs/adr/README.md`
- Tests: `tests/ai/review/test_review_runner_executor.py`, `tests/roadmap/test_roadmap_runner_tools.py`

## Feasibility

- The probes answer with the line "The path `src/devops_cli/core/process_hardening.py` is a file of the staging commit." and the line "The path `src/devops_cli/roadmap/runner_tools.py` is a file of the staging commit."
- The probes answer with the line "The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`, `tests/fixtures/research/repo/src/devops_cli/tools_lock/tools.lock`. No commit in the history deleted or renamed it."
- The probes answer with the line "Not probed, the bound of 10 commands is reached: `also.review`, `scanner.from`, `and.from`, `it.path`, `runner.Kubernetes`, `process.Kubernetes`, `bubblewrap`, `unshare`, `NOT_IN_RUNNER`, `RuntimeDefault`, `RUNNER_TOOLS`", so each of those names was confirmed with a tool call of this run and not with a probe line.
- `read_file` of `src/devops_cli/core/process_hardening.py` lines 12-24 shows `src/devops_cli/core/process_hardening.py:19:seccomp profile refuses. So the job guarantees an`, in the sentence whose line 18 says that a user namespace needs `unshare`: the premise of the issue holds.
- `read_file` of `src/devops_cli/security/tool_executor.py` lines 640-700 shows `src/devops_cli/security/tool_executor.py:666:class DirectToolExecutor:`, the docstring line `src/devops_cli/security/tool_executor.py:671:tools, which are not reviews. A review never runs its tools here.` and `src/devops_cli/security/tool_executor.py:690:executor=CONST_TOOL_EXECUTOR_DIRECT,`, so the direct executor already records its runs as direct and only its docstring refuses a review.
- `read_file` of `src/devops_cli/ai/review/runner.py` lines 1360-1435 shows `src/devops_cli/ai/review/runner.py:1369:def execute_review_workflow(`, the docstring line `src/devops_cli/ai/review/runner.py:1398:The review runs its tools in the sandbox, and in no other place.` and `src/devops_cli/ai/review/runner.py:1421:executor = SandboxToolExecutor()`, so a review builds one sandbox executor today and the change threads the runner profile into that one call.
- `search_code` for `execute_review_workflow(` shows five calls in `src/devops_cli/commands/review.py`, at lines 300, 658, 683, 741 and 764, such as `src/devops_cli/commands/review.py:300:execute_review_workflow(`, so the command passes the setting at five places and the default keeps the sandbox.
- `search_code` for `in_runner` shows `docs/CONFIGURATION.md:311:effort=['low', 'medium'] in_runner=False`, `docs/ENV_VARS.md:227:Whether this process is the pod of a runner Job.` and `src/devops_cli/config/settings.py:1459:Whether this process is the pod of a runner Job.`, so the setting exists and only the runner template sets it.
- `read_file` of `src/devops_cli/ai/review/pipeline.py` lines 915-950 shows `src/devops_cli/ai/review/pipeline.py:927:ANALYZER_NOT_INSTALLED = "not installed"` and `src/devops_cli/ai/review/pipeline.py:932:STATIC_ANALYZERS: tuple[tuple[str, str, str], ...] = (` with 8 entries at lines 933-941: Bandit, Kube-linter, Pluto, Trivy, Semgrep, Gitleaks, osv-scanner and golangci-lint. Each member has a decision: Bandit and Trivy stay because `RUNNER_TOOLS` already holds them, Kube-linter stays out because #3562 and #5394 own it, and the other five join the image.
- `read_file` of `src/devops_cli/ai/review/pipeline.py` lines 977-990 shows `src/devops_cli/ai/review/pipeline.py:985:if not files_by_kind.get(kind):` and `src/devops_cli/ai/review/pipeline.py:986:states[name] = ANALYZER_NO_FILES`, and `file_symbols` of the same file shows `src/devops_cli/ai/review/pipeline.py:def static_analyzer_states` at line 977 and `src/devops_cli/ai/review/pipeline.py:def classify_scanner_files` at line 1530, so the fail-closed rule reads the review's own analyzer states and a Python diff leaves Kube-linter at `no files`.
- `read_file` of `src/devops_cli/tools_lock/tools.lock` lines 298-310 and 458-520 shows `src/devops_cli/tools_lock/tools.lock:304:[binary.pluto]` at `src/devops_cli/tools_lock/tools.lock:305:version = "5.24.4"`, `src/devops_cli/tools_lock/tools.lock:462:[binary.gitleaks]` at `src/devops_cli/tools_lock/tools.lock:463:version = "8.30.1"`, `src/devops_cli/tools_lock/tools.lock:489:[binary.osv-scanner]` at `src/devops_cli/tools_lock/tools.lock:490:version = "2.6.0"` and `src/devops_cli/tools_lock/tools.lock:512:[binary.golangci-lint]` at `src/devops_cli/tools_lock/tools.lock:513:version = "1.64.8"`, so four added scanners are pinned binaries with a SHA-256 per platform and the lock file needs no change.
- `search_code` for `[python.semgrep]` shows `src/devops_cli/tools_lock/tools.lock:571:[python.semgrep]`, and `read_file` of lines 568-585 shows `src/devops_cli/tools_lock/tools.lock:572:version = "1.179.0"` and `src/devops_cli/tools_lock/tools.lock:575:requirements = "semgrep.txt"`, so Semgrep is a Python tool of the same lock and `devops install-tools --tool semgrep` installs it at its pinned version.
- `list_files` of `src/devops_cli/tools_lock` shows `src/devops_cli/tools_lock/semgrep.txt`, the requirements file that the Semgrep entry names.
- `read_file` of `Dockerfile` lines 70-180 shows `Dockerfile:89:FROM builder AS runner-tools`, `Dockerfile:91:--tool promtool --target-dir /opt/devops-tools/bin` and `Dockerfile:165:RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools python -m devops_cli.roadmap.runner_tools`, the install form that the change repeats for each added scanner and the last step that checks every tool of the table.
- `read_file` of `docs/CLUSTER.md` lines 55-70 shows `docs/CLUSTER.md:66:no tool that fails the image scan` and `docs/CLUSTER.md:66:trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --ignorefile .trivyignore`, so the scan of the built image is the check of the image criterion.
- `read_file` of `src/devops_cli/roadmap/runner_tools.py` lines 30-45 shows the constants the plan relies on: `src/devops_cli/roadmap/runner_tools.py:38:TOOLS_DIR = Path("/opt/devops-tools")`, `src/devops_cli/roadmap/runner_tools.py:39:TOOLS_BIN_DIR = TOOLS_DIR / "bin"`, `src/devops_cli/roadmap/runner_tools.py:40:USER_DATA_ROOT_VARIABLE = "DEVOPS_CLI_USER_DATA_ROOT"` and `src/devops_cli/roadmap/runner_tools.py:43:UV_VERSION = "0.13.8"`, the directory, the variable and the pin that each new `devops install-tools --tool <name> --target-dir /opt/devops-tools/bin` line uses.
- The verify programs are `uv` (source `IMAGE_PIN`, the pin `UV_VERSION` of 0.13.8), `devops` (source `PROJECT`), `pytest` (source `DEV_GROUP`) and `git` (source `APT`), each an entry of `src/devops_cli/roadmap/runner_tools.py:94:RUNNER_TOOLS: tuple[RunnerTool, ...] = (`; the runner pod sets `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `runAsNonRoot: true`.
- A failing test is failure class `test` with action `repair`; a program that a step may not start is `refused_tool` with action `wait`; a command that runs past its limit is `timeout` with action `retry`.
- `docker` is an entry of `src/devops_cli/roadmap/runner_tools.py:202:NOT_IN_RUNNER: dict[str, str] = {` with the reason that no check, hook, test or job of the gate runs it, and `trivy` is an entry of `RUNNER_TOOLS` at `gate:static`; a container build of the image is no runner step, so the image build and its scan are the manual process of group 4.
- `list_files` of `docs/adr` shows the newest record is `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, so the new record is 0028, and `read_file` of `docs/adr/README.md` lines 18-45 shows the key row `docs/adr/README.md:26:The number of the issue that asked for the decision.` and the approval step `docs/adr/README.md:39:gives the hash of the body when the front matter has none`.
- `read_file` of `docs/adr/README.md` lines 140-176 shows the generated index that the new record must join: `docs/adr/README.md:142:writes this table from the front matter of each record, and` and `docs/adr/README.md:174:| [0027](0027-dependency-updates-come-from-self-hosted-renovate.md) | Dependency updates come from self-hosted Renovate | proposed | 2026-11-16 |`, so the test `tests/invariants/test_adr_records.py:25:assert sync_index(page, read_record_texts(ADR_DIRECTORY)) == page` fails on a record whose row the table lacks; the correction of the review finding adds `docs/adr/README.md` to the `changes` of group 4 and regenerates the index there.
- `read_file` of `src/devops_cli/docs/generator.py` lines 1318-1333 shows `src/devops_cli/docs/generator.py:1326:index_page = docs / ADR_INDEX_PAGE` and `src/devops_cli/docs/generator.py:1328:synced = sync_index(`, so `uv run devops docs generate` writes the table of `docs/adr/README.md` and no hand edit of it survives the docs check.
- `list_files` of `docs` shows `docs/ERRORS.md`, and `list_files` of `tests/docs` shows `tests/docs/test_exceptions.py`, the catalog and the test that holds each error class to its row.
- `read_issue` of #3562 shows it open for `kubectl` and `kube-linter`, with `kube-linter` split to #5394, and `read_issue` of #3108 shows it closed after actionlint 1.17.1, shellcheck and Trivy passed the image scan; the change adds no tool that those items add.
- `execute_review_workflow` and `review_tool_executor` need a checkout of the repository at the staged commit for their tests, and no client and no network: the tests double the process edges and set PATH, so they reach no network, no cluster and no real scanner.
- `uv run devops docs generate` needs a checkout of the repository and no network; `devops install-tools` in the image build needs a network to fetch each pinned release, so no group runs it.
- The first checks of the implementation are `uv run devops ci test tests/ai/review/test_review_runner_executor.py`, `uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`, `uv run devops docs generate` followed by `uv run devops ci test tests/invariants/test_adr_records.py`, and on a workstation with a container engine `docker build --target runner -t runner-review .`, `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 runner-review` and `docker run --rm -e DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools --entrypoint python runner-review -m devops_cli.roadmap.runner_tools`.

## Existing Tool Considered

The change reuses `src/devops_cli/security/tool_executor.py:class DirectToolExecutor`, the `ToolExecutor` seam, and the five scanners that `src/devops_cli/tools_lock/tools.lock` already pins, which `devops install-tools` installs. Each scanner is an open, maintained release with a checksum in the lock. The change builds no sandbox and writes no scanner of its own.

## Dependencies

None.

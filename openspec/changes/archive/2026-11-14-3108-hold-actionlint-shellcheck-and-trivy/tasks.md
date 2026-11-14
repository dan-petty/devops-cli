# Tasks

## 1. Hold the three tools in the runner image

Kind: behavior. Reads: `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`. Changes: `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`, `tests/roadmap/test_roadmap_runner_tools.py`.

- [x] 1.1 Move `actionlint`, `shellcheck` and `trivy` into `RUNNER_TOOLS` with the source of each, remove them from `NOT_IN_RUNNER`, and set `HOOK_PROGRAMS` empty
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` passes
- [x] 1.2 Add the pinned actionlint image stage, copy its binary, install shellcheck from apt, and install Trivy in the `runner-tools` stage
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` passes
- [x] 1.3 Replace the test that held the tools out with a test that they are held at the pins of their sources
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py` passes

## 2. Name the tools in the documents

Kind: other. Reads: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Say that the runner image holds actionlint, shellcheck and Trivy since their releases passed the scan
  - Verification: `$ uv run devops ci docs` passes

## 3. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 3.1 Run the whole gate of the branch
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py tests/roadmap/implement/test_roadmap_implement_hooks.py` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
- [x] 3.2 The Runner Image check of the pull request builds the image and scans it
  - Verification: `$ uv run devops pr checks` shows `Runner Image` pass

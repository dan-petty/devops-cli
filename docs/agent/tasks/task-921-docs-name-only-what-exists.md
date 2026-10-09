# Task: Hand-Written Docs Name Only Commands, Options, and Architecture Patterns That Exist (#921)

**Issue**: [#921](https://github.com/dan-petty/devops-cli/issues/921)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/docs

## Description
The hand-written documentation files (`ARCHITECTURE.md`, `README.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/VISION.md`, `k8s/README.md`, and `k8s/llm/profiles/README.md`) contained references to non-existent or deprecated commands, incorrect option flags, removed architecture classes/protocols (`ProcessExecutionPipeline`, `@cli_command_handler`, `StagePipeline`), out-of-date GPU inference profiles/tiers, and inaccurate CI/SDLC checks.

To permanently prevent documentation drift, the static Markdown command line argv collector was extended to collect and validate command references across all hand-written documentation files. The collector maps standard documentation placeholders such as `<ver>]` and `[ARGS]...` to `ArgvPlaceholder`; since #1299, an option written inside optional-group brackets (`[-v`) is validated as that option. Hand-written documentation validation is integrated directly into `DocGenerator.check_docs()` and executed on `devops docs check` and throughout CI. All verified defects across the 9 hand-written documentation files were rectified.

## Key Changes
- **Constants & Configuration** (`src/devops_cli/config/constants.py`):
  - Defined `CONST_DOCS_ARGV_KNOWN_PLACEHOLDERS` (`COMMAND`, `ARGS`, `OPTIONS`, `SUBCOMMAND`, `PARAMS`) and `CONST_HANDWRITTEN_DOCS_PATHS` covering the 9 canonical hand-written documentation paths.
- **Markdown Argv Collector & Placeholders** (`src/devops_cli/docs/markdown_argv_collector.py`):
  - Updated `is_placeholder()` to recognize known uppercase placeholder tokens and bracketed words (e.g., `<ver>]`); since #1299, the option in `[-v` is validated rather than read as a placeholder.
  - Added `collect_handwritten_docs_argv_references(root_dir)` and `check_handwritten_docs_argv(root_dir)`.
- **Docs Check Integration** (`src/devops_cli/docs/generator.py`):
  - Wired `check_handwritten_docs_argv(self.root_dir)` into `DocGenerator.check_docs()` so `devops docs check` continuously audits hand-written documentation alongside MCP tools and the offline knowledge base.
- **Hand-Written Documentation Verification Tests** (`tests/test_docs_knowledge_base_argv.py`):
  - `test_every_handwritten_doc_argv_resolves`: Verifies that every `devops` command across all hand-written documentation files statically resolves with zero errors and no subprocess execution.
  - `test_docs_check_reports_an_unresolved_handwritten_doc_argv`: Verifies that `devops docs check` detects and reports unresolvable commands in hand-written files.
  - `test_handwritten_docs_defective_reference_fails_resolution`: Verifies that defective commands (e.g. `devops pr merge`, `devops scan kubelinter`) fail resolution.
- **Documentation Fact Alignment**:
  - `ARCHITECTURE.md`: Replaced `devops devcontainer run-lifecycle` with `post-create` / `post-start`, updated history path to `~/.bash_history`, updated T4 to commit signing, fixed `devops ci run` -> `devops ci`, and rewrote Section 7 to eliminate phantom classes (`@cli_command_handler`, `ProcessExecutionPipeline`, `StagePipeline`).
  - `README.md`: Added Challenger persona, lifecycle commands, corrected timeout constants, documented checksum verification nuances, and updated milestone deliverables span (`v0.0.1` to `v0.3.5`).
  - `RELEASE_CYCLE.md`: Updated CI checks list, line coverage threshold (90%), `devops release tag -v`, `pyproject.toml` version detection, `--skip-ci` verification, and links to `docs/ROADMAP.md`.
  - `docs/SDLC.md`: Updated line coverage (90%), pre-commit hooks diagram and list (`structural-invariants`, `devops-ci-test-changed`), CI check names, manual labels audit, views sync, CodeQL push trigger, and release runbook link.
  - `docs/ROUTINE_TASKS.md`: Updated CI checks list, worker cap `-n logical`, `pr create --title`, `gh pr merge`, manifest scan commands (`k8s lint`, `check-deprecated`, `scan trivy --type iac`), complexity note, `telemetry logfire`, `repos list`, project grounding with audit/template, In Progress transition, pyproject.toml version bump, bandit command, SSRF wording, devcontainer lifecycle, and SSH audit.
  - `docs/DEVCONTAINER_USAGE.md`: Specified `linux/amd64` architecture, clarified `tofu`/`terraform` and security scanners manual install requirements, image tag comment, `.mcp.json` / `CLAUDE.md`, `review branch --all`, Minikube GPU/addons notes, `deploy-stack --stack` examples, and `stream-logs`.
  - `docs/VISION.md`: Clarified item 6 (`devops scan aibom` flags `trust_remote_code` and compiles AIBOM records, while automated GPU provisioning gating is a visionary theme).
  - `k8s/README.md`: Updated stack table (infra, llm, logging, all), minikube post-start, port-forward `ollama-16gib`, LLM gateway models & routes, Ollama VRAM tiers, review weights, tune measurement, context window, DaemonSet GPU placement, diagram namespace labels, removed `--context` and `-k` from apply, and updated argo cd apps status.
  - `k8s/llm/profiles/README.md`: Set deployed backend to Ollama, corrected matrix TP/PP (2) and quantization (AWQ, FP8), updated ClusterIP services to Ollama tiers, and replaced gateway config YAML block with configmap excerpt.

## Acceptance Criteria
- [x] Every finding from Issue #921 is corrected across all 9 hand-written documentation files.
- [x] Unused architecture classes/protocols (`ProcessExecutionPipeline`, `@cli_command_handler`, `StagePipeline`) are removed from `ARCHITECTURE.md`.
- [x] Command-resolution tests cover `README.md`, `ARCHITECTURE.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/VISION.md`, `k8s/README.md`, and `k8s/llm/profiles/README.md`.
- [x] Placeholder token handling supports known CLI argument conventions (`COMMAND`, `ARGS`, `OPTIONS`, `SUBCOMMAND`, `PARAMS`, `[-v <ver>]`).
- [x] `tests/test_docs_knowledge_base_argv.py` verifies static resolution of hand-written docs, check failure reporting, and defective command rejection.
- [x] `devops docs check` runs with 0 errors.
- [x] `uv run devops ci` completes with 100% passing status and $\ge 90\%$ code coverage.

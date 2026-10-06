# Task: Knowledge Base Names Only Commands, Options, and Components That Exist (#920)

**Issue**: [#920](https://github.com/dan-petty/devops-cli/issues/920)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/docs

## Description
The bundled offline AI knowledge base under `src/devops_cli/ai/knowledge_base/` contained command examples, option flags, settings classes, environment variables, and third-party library versions that were outdated, inaccurate, or non-existent (e.g. `devops argo list`, `devops scan security`, `devops docker prune --all`, `DEVOPS_CLI_CONFIG_PATH`, `DEVOPS_CLI_LOG_LEVEL`, `UnifiedLLMClient`, `nomic-embed-text`, and numbered gate references).

To ensure permanent accuracy and prevent documentation drift, a static Markdown command line argv collector was implemented and wired directly into `devops docs check` (alongside MCP server argv verification). Every command line and inline code reference in the knowledge base is now statically validated against Click command trees. All 80 knowledge base articles were updated to reflect exact, working CLI commands, current `pyproject.toml` dependency versions, and unified Gated quality standards.

## Key Changes
- **Markdown Argv Collector** (`src/devops_cli/docs/markdown_argv_collector.py`):
  - Extracted fenced code blocks (`bash`, `sh`, `zsh`, `shell`, `console`) and inline code spans (`devops ...`) across markdown files.
  - Stripped shell comments, pipes, and compound operators (`|`, `;`, `&&`) while preserving quoted strings.
  - Tokenized shell commands and mapped variable expressions (`<placeholder>`, `{placeholder}`, `[placeholder]`) to `ArgvPlaceholder`.
  - Resolved command argv tuples statically against Click CLI commands via `resolve_devops_argv()`.
  - Provided `collect_knowledge_base_argv_references(root_dir)` and `check_knowledge_base_argv(root_dir)`.
- **Docs Check Verification Integration** (`src/devops_cli/docs/generator.py`):
  - Integrated `check_knowledge_base_argv(self.root_dir)` into `DocGenerator.check_docs` so `devops docs check` and CI quality gates verify knowledge base commands alongside MCP server references.
- **Knowledge Base Verification Test Suite** (`tests/test_docs_knowledge_base_argv.py`):
  - `test_collect_markdown_argv_references_fixture`: Tests parsing fenced lines, inline spans, placeholders, and trailing comments.
  - `test_docs_check_reports_an_unresolved_knowledge_base_argv`: Tests failure reporting and formatting when an unresolvable command line is found.
  - `test_every_knowledge_base_argv_resolves`: Verifies that every `devops` command in the 80 knowledge base files resolves statically with no subprocess execution (`subprocess.Popen` guarded).
- **Knowledge Base Articles Remediation**:
  - `README.md`: Updated package and command counts, replaced numbered gate references with Gated CI standards, added Challenger persona, updated `tldextract` description.
  - `devops_cli/cli_command_reference.md`: Rewrote command tables to full `devops <group> <subcommand>` spans matching Click trees.
  - `devops_cli/configuration_and_settings.md`: Synced settings table with `settings.py`, replaced `DEVOPS_CLI_CONFIG_PATH` with `DEVOPS_CLI_CONFIG`, removed `DEVOPS_CLI_LOG_LEVEL`, updated task overrides.
  - `devops_cli/architecture.md`: Updated review topology to include Challenger persona, output `<persona>-review.md`, corrected `devops config get/set` and language catalog paths.
  - `devops_cli/python_packages.md`: Synced all pinned package versions with `pyproject.toml`, updated module paths and class names.
  - `devops_cli/libraries/*.md` (all 23 files): Synced versions with `pyproject.toml`, adjusted relative links to 6 segments (`../../../../../../src/devops_cli/`), and corrected CLI examples and symbol references.
  - `devops_cli/tasks/*.md`: Corrected CLI examples, settings names, and options across all task files.
  - `it_domains/tools/*.md` & `it_domains/topics/*.md`: Replaced outdated or non-existent CLI subcommands and options (`argo cd apps`, `scan trivy`, `scan sast`, `scan secrets`, `scan report`, `tf`, `valkey`, `k8s deploy-stack --stack`, `k8s lint/audit/check-deprecated`, `qwen3-embedding:0.6b`).

## Acceptance Criteria
- [x] Markdown command lines and inline code spans in `src/devops_cli/ai/knowledge_base/**/*.md` are extracted and tokenized, mapping bracketed placeholders to `ArgvPlaceholder`.
- [x] Extracted argv tuples are statically resolved against CLI Click command trees using `resolve_devops_argv()`.
- [x] Markdown argv check is integrated into `DocGenerator.check_docs()` and reported by `devops docs check`.
- [x] `tests/test_docs_knowledge_base_argv.py` verifies extraction fixtures, check failure reporting, and that every knowledge base command line resolves without subprocess execution.
- [x] All 80 knowledge base articles name only real commands, options, settings, environment variables, and pinned library versions.
- [x] Negative invariants satisfied: zero numbered gate terminology, zero phantom settings (`DEVOPS_CLI_CONFIG_PATH`, `DEVOPS_CLI_LOG_LEVEL`), zero obsolete models (`nomic-embed-text`), zero removed `#767` names (`github.token`).
- [x] `uv run devops ci` completes with 100% passing status and $\ge 90\%$ code coverage.

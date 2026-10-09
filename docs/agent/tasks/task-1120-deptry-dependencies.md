# Task: pyproject.toml Declares Every Package src Imports, and a deptry Step in devops ci Keeps It That Way (#1120)

**Issue**: [#1120](https://github.com/dan-petty/devops-cli/issues/1120)  
**Status**: Done  
**Milestone**: v0.2.31  
**Priority**: priority/p2-medium  
**Scope**: scope/ai  

## Description
Prior to this task, `pyproject.toml` omitted several packages imported directly in `src/` (such as `logfire`, `pynacl`, `openai`, `pydantic-graph`, `opentelemetry-api`, and `secretstorage`), relying on transitive resolution through packages like `pydantic-ai` or `keyring`. Furthermore, fallback shims in `src/devops_cli/http/broker.py` and `src/devops_cli/telemetry/memory_profiler.py` and settings re-exports in `src/devops_cli/ai/settings/__init__.py` retained vestigial `httpx` imports despite the project standardizing on `httpx2`.

To enforce strict dependency hygiene:
1. `deptry` was integrated into the local CI suite as a dedicated gate check (`deps`, invoking `uv run deptry src`) and CLI subcommand (`devops ci deps`).
2. All packages directly imported across `src/` were declared in `pyproject.toml`, using `pydantic-ai[spec]` for `pydantic-handlebars`.
3. `[tool.deptry.per_rule_ignores]` was configured for dynamically loaded tree-sitter grammars (DEP002) and optional durable workflow engines (DEP001).
4. All residual `httpx` imports and fallback shims across `src/` were eliminated, updating `ModelSettings.timeout` handling to accept `float | None`.

## Key Changes
- **Dependency Declarations & Configuration** (`pyproject.toml`, `uv.lock`):
  - Declared direct pins: `logfire==5.1.0`, `pynacl==1.6.2`, `openai==3.26.1`, `pydantic-graph==2.54.0`, `opentelemetry-api==1.44.0`, and `secretstorage==3.5.0; sys_platform == 'linux'`.
  - Switched `pydantic-ai==2.54.0` to `pydantic-ai[spec]==2.54.0` (which provides `pydantic-handlebars` and `PyYAML`).
  - Added `deptry==0.25.1` to `[dependency-groups].dev`.
  - Configured `[tool.deptry.per_rule_ignores]` ignoring DEP002 for `tree-sitter` and grammar wheels, and DEP001 for `temporalio`, `dbos`, and `prefect`.
- **Elimination of Vestigial `httpx` Imports & Shims** (`src/`):
  - `src/devops_cli/ai/settings/__init__.py`: Removed `httpx.Timeout` re-export; updated `create_model_settings` and `resolve_runtime_model_settings` to accept numeric seconds as `float | None`.
  - `src/devops_cli/ai/agents/pydantic_agent.py`, `src/devops_cli/ai/agents/__init__.py`, and `src/devops_cli/ai/__init__.py`: Removed `Timeout` from lazy imports and `__all__`.
  - `src/devops_cli/http/broker.py` & `src/devops_cli/telemetry/memory_profiler.py`: Removed `httpx` fallback try/except blocks; imported `httpx2` directly.
  - `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai.md`: Updated code snippet to use `httpx2.AsyncClient(timeout=httpx2.Timeout(15.0))`.
- **CI Quality Gate Integration** (`src/devops_cli/commands/ci.py`, `messages.py`, `help.py`, `AGENTS.md`):
  - Added `CheckSpec(name="deps", display_title=MESSAGES.ci.deps, cmd=["uv", "run", "deptry", "src"], span_name="ci.step.deps", metric_step="deps")` into `get_check_specs()`.
  - Added `devops ci deps` CLI command with dry-run support.
  - Added localized messages and help strings.
  - Updated `AGENTS.md` and synchronized documentation matrices via `devops docs generate --sync-readme`.
- **Test Suites** (`tests/test_ci.py`, `tests/test_pydantic_ai_settings.py`):
  - Added `test_gate_deps_step_spec` asserting exact check specification argv (`["uv", "run", "deptry", "src"]`).
  - Added `("deps", "deps")` to `test_subcommand_dispatches_exact_table_row_cmd`.
  - Verified `test_ci_workflow_parity_with_check_table` passes without workflow modification because `static` job runs `--skip test,outdated`.

## Acceptance Criteria
- [x] `deptry src` passes cleanly with zero findings on the codebase.
- [x] Direct dependencies (`logfire`, `pynacl`, `openai`, `pydantic-graph`, `opentelemetry-api`, `secretstorage`) are declared in `pyproject.toml`.
- [x] All residual `httpx` imports and fallback shims in `src/` are removed; `Timeout` re-export is eliminated from `devops_cli.ai.settings`.
- [x] `devops ci deps` executes `uv run deptry src` and is wired as a gate check in `devops ci`.
- [x] `AGENTS.md` and documentation matrices are synchronized with the `deps` gate check.
- [x] Test suite covers `deps` check spec, CLI subcommand dispatch, and workflow parity.
- [x] Verified failure modes: adding `import httpx` triggers DEP003; removing a declared package triggers DEP002.
- [x] `uv run devops ci` passes 100% locally.

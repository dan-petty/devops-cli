# Proposal

## Why

Issue #917: `get_run` in `src/devops_cli/ai/run_store.py` validates `run_id` with `re.match(r"^[a-zA-Z0-9_\-\.]+$", run_id)`.
The `$` anchor matches before a trailing newline.
An identifier such as `"abc\n"` passes the check and reaches the filesystem glob pattern.
Similar identifier checks in `src/` use `re.match` with `$` and must use `re.fullmatch`.

## What Changes

- Update `get_run` in `src/devops_cli/ai/run_store.py` to use `re.fullmatch`.
- Add a test that verifies `get_run("abc\n")` returns `None` without globbing.
- Update `re.match` identifier checks in `src/devops_cli/core/validation.py` to use `re.fullmatch`.
- Update `re.match` identifier checks in `src/devops_cli/telemetry/memory_profiler.py` to use `re.fullmatch`.
- Update `re.match` identifier checks in `src/devops_cli/ai/mcp/server.py` and `src/devops_cli/ai/harness/skills.py` to use `re.fullmatch`.
- Update `re.match` identifier checks in `src/devops_cli/commands/grafana.py`, `src/devops_cli/commands/pipeline.py`, and `src/devops_cli/commands/uv.py` to use `re.fullmatch`.
- Update compiled identifier regex matches in `src/devops_cli/commands/branches.py`, `src/devops_cli/git/operations.py`, and `src/devops_cli/k8s/template.py` to use `fullmatch`.
- This change alters no behavior that a consumer observes outside validation of invalid identifiers with trailing newlines. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/run_store.py`: `get_run` validates `run_id` with `re.fullmatch`.
- `src/devops_cli/core/validation.py`: `validate_k8s_context_name` and `validate_session_id` validate inputs with `re.fullmatch`.
- `src/devops_cli/telemetry/memory_profiler.py`: `profile_memory` target validation uses `re.fullmatch`.
- `src/devops_cli/ai/mcp/server.py`: `hydrate_tool_domain` key validation uses `re.fullmatch`.
- `src/devops_cli/ai/harness/skills.py`: `normalize_skill_name` validates normalized name with `re.fullmatch`.
- `src/devops_cli/commands/grafana.py`: `dashboards_export` validates `uid` with `re.fullmatch`.
- `src/devops_cli/commands/pipeline.py`: `pipeline_run` validates `function_name` with `re.fullmatch`.
- `src/devops_cli/commands/uv.py`: `install` validates `version` with `re.fullmatch`.
- `src/devops_cli/commands/branches.py`: `jira` validates `ticket_id` with `_JIRA_RE.fullmatch`.
- `src/devops_cli/git/operations.py`: `_is_safe_revision` validates revision with `CONST_SAFE_GIT_REF_PATTERN.fullmatch`.
- `src/devops_cli/k8s/template.py`: `normalize_domain` validates domain with `CONST_K8S_SUBDOMAIN_RE.fullmatch`.
- `tests/test_run_store.py`: Test asserting `get_run("abc\n")` returns `None` without calling glob.

## Feasibility

- Premise confirmed against CPython 3.14.7 regular expression engine documentation and runtime evaluation.
- `re.match(r"^[a-zA-Z0-9_\-\.]+$", "abc\n")` returns a match object because `$` matches before a newline.
- `re.fullmatch(r"^[a-zA-Z0-9_\-\.]+$", "abc\n")` returns `None` because the string ends with a newline.
- Code inspection at base `f730cdbc`: `get_run` in `src/devops_cli/ai/run_store.py:414` invokes `Path.glob` when `re.match` succeeds.

## Existing Tool Considered

The Python standard library `re.fullmatch` function covers the requirement directly.
No third-party library is required.
No internal code is deleted.

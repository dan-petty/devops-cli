# Task 645: Resolve Pluto Single File Scan Timeout and Telemetry Typing Errors

**Issue**: [#645](https://github.com/dan-petty/devops-cli/issues/645)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

During reviews and telemetry trace inspections in OpenTelemetry / Jaeger (`http://localhost:16686`), repeated `subprocess.TimeoutExpired` errors occurred during manifest deprecation scans:
```
subprocess.TimeoutExpired: Command '['pluto', 'detect-files', '-f', '/workspaces/devops-cli/k8s/...', '-o', 'json']' timed out after 60.0 seconds
```

### Root Cause
1. **Pluto Subprocess Timeout**: In `src/devops_cli/security/pluto.py`, `PlutoScanner.build_command` constructed commands using `pluto detect-files -f <file> -o json`. In the Pluto CLI, `-f` (`--additional-versions`) expects a YAML file containing custom deprecated API versions, not the target scan path. Consequently, Pluto defaulted its directory `-d` flag to `.` and recursively walked the entire project tree (including large subdirectories and virtual environments), hanging for 60 seconds per manifest file before timing out. The correct command for single file scanning is `pluto detect <path> -o json`, while directory scanning uses `pluto detect-files -d <directory> -o json`.
2. **Telemetry Test Module Export Error**: In `tests/test_telemetry_collector_export.py`, importing `from devops_cli.commands import telemetry as telemetry_commands` and monkeypatching `telemetry_commands.OTelTelemetryClient` failed strict static type analysis (`[attr-defined]`) due to explicit `__all__` boundaries in `devops_cli.commands`.

### Key Deliverables Completed:
- [x] **Add `CONST_K8S_MANIFEST_EXTENSIONS` Constant** (`src/devops_cli/config/constants.py`, `src/devops_cli/config/__init__.py`):
  - Defined exhaustive manifest extensions set `frozenset({".yaml", ".yml", ".json"})` in `constants.py` per architectural standards.
- [x] **Pluto File vs Directory Command Dispatch** (`src/devops_cli/config/commands.py`, `src/devops_cli/security/pluto.py`, `src/devops_cli/ai/tools/builtin_tools.py`):
  - Updated `build_pluto_cmd` in `src/devops_cli/config/commands.py` to route file paths to `pluto detect <file> -o json` and directory paths to `pluto detect-files -d <directory> -o json`.
  - Updated `PlutoScanner.build_command` in `src/devops_cli/security/pluto.py` and `scan_pluto` in `src/devops_cli/ai/tools/builtin_tools.py` to delegate directly to `build_pluto_cmd`.
- [x] **Direct Telemetry Client Typing in Tests** (`tests/test_telemetry_collector_export.py`):
  - Replaced non-exported `telemetry_commands.OTelTelemetryClient` monkeypatch target with direct `OTelTelemetryClient` from `devops_cli.telemetry.tracer`, resolving all mypy `[attr-defined]` errors.
- [x] **Embeddings Test Telemetry Isolation** (`tests/test_rag_embeddings.py`):
  - Filtered `_capture_embedding_posts` to intercept and record only embedding endpoint POST requests, preventing asynchronous OTLP metrics posts from polluting expected embedding assertion queues.
- [x] **Consolidated Structural Test Assertions** (`tests/test_command_builders.py`, `tests/test_secops.py`, `tests/test_builtin_tools.py`):
  - Added unit test cases verifying `pluto detect` for individual manifest files and `pluto detect-files -d` for directories.
  - Consolidated assertions into structural tuple equality checks adhering to the $M \le 10$ cyclomatic complexity invariant.
- [x] **100% Passing Gated CI Quality Checks** (`uv run devops ci`).

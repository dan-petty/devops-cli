# Design: Aqua Trivy SBOM Generation

## Overview

The `devops scan sbom` command produces Software Bill of Materials (SBOM) documents. Previously, it constructed dictionary objects manually without validation against CycloneDX or SPDX JSON schemas. Furthermore, dependency inspection inspected Python packages from `uv.lock` or the running Python environment, leading to invalid inventories for non-Python projects.

This design transitions `devops scan sbom` to execute Aqua Trivy (`trivy fs`) through the existing security scanner integration architecture.

## Architecture

1. **Command Construction**:
   `src/devops_cli/config/commands.py` defines `build_trivy_sbom_cmd(target, format_type)`. For format `cyclonedx` (or `json`), it formats `["trivy", "fs", "--format", "cyclonedx", str(target)]`. For format `spdx` (or `spdx-json`), it formats `["trivy", "fs", "--format", "spdx-json", str(target)]`.

2. **Scanner Base Integration**:
   `src/devops_cli/security/sbom.py` defines `TrivySbomScanner` inheriting from `TrivyScanner` (and `BaseSecurityScanner`).
   `run_trivy_sbom` runs the command using `self._run_tool`, routing through `ToolExecutor` and ensuring environment isolation and test seams (`process_fake`).

3. **Output Streaming**:
   `scan_sbom` receives the completed process stdout from Trivy and writes it directly to the target file or standard output without serialization mutations.

4. **Error Handling**:
   Pre-flight checks verify `check_binary("trivy")`. If missing, `print_error` reports `Required dependency 'trivy' is not installed.` and exits with code 1.

## Rejected Alternatives

### 1. Maintain in-process CycloneDX dictionary generation with cyclonedx-python-lib
- **Alternative**: Adopt `cyclonedx-python-lib` (11.12.0) to construct CycloneDX documents in Python.
- **Rejection Evidence**: Aqua Trivy is already installed and managed as the primary vulnerability scanner in devops-cli (`src/devops_cli/tools_lock/tools.lock`). Adding a Python library would introduce duplicate dependency extraction logic and would not cover non-Python project ecosystems natively.

### 2. Invoke bare `subprocess.run` directly in `commands/scan.py`
- **Alternative**: Execute `trivy` with Python's standard `subprocess.run` inside `commands/scan.py`.
- **Rejection Evidence**: Bypasses the unified `BaseSecurityScanner` and `ToolExecutor` seam, preventing hermetic process mocking with `process_fake` and breaking sandbox isolation.

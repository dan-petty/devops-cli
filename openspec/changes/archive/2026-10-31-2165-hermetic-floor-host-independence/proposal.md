# Change: Hermetic Floor Host Independence

## Problem
The hermetic test floor leaves some host state visible to tests. The same test can take different execution paths in the devcontainer and on a stock GitHub Actions runner.
1. Tokenizer cache: `_resolve_tiktoken_cache_dir` falls back to `/usr/local/share/tiktoken/` when environment variables are unset. The devcontainer image holds BPE files there, but runner environments do not. Tests observe different token counts across hosts.
2. Mounts: `ci/diagnostics.py` reads `/proc/mounts` directly on the host when no mounts text is supplied.
3. Process table: `k8s/port_forward_daemon.py` reads `/proc/<pid>/stat` from real host processes.
4. PATH and program lookups: `scanner_fake` appends the host's `PATH`, allowing unrecorded host binaries to be discovered.
5. Host-decided skips: Tests use `pytest.skip` when detecting host conditions such as symlink permissions, non-UTF-8 filesystem paths, and `/proc` availability.

## Proposed Change
1. Floor isolation for tokenizer cache: Direct `TIKTOKEN_CACHE_DIR` and `DATA_GYM_CACHE_DIR` to an empty temporary directory by default in the test floor so all hosts calculate identical token counts.
2. Mounts and process table isolation: Configure `ci/diagnostics.py` and `k8s/port_forward_daemon.py` to use fixed tables in tests so tests do not read `/proc`.
3. Hermetic `PATH`: Set `PATH` in `scanner_fake` to include only the fake stand-ins directory and the Python interpreter directory.
4. Floor guard for host paths: Install a guard in `tests/conftest.py` that fails any test attempting to open files under `/proc`, `/usr/local/share/tiktoken`, or host paths outside the test temporary directory, the repository, and the Python interpreter.
5. Remove host-decided skips: Remove host skips for symlinks, `/proc`, and non-UTF-8 paths so tests execute uniformly across all hosts.

## Feasibility
Confirmed against repository code and test execution:
- `src/devops_cli/ai/context_budget.py` prioritizes `TIKTOKEN_CACHE_DIR` from environment variables.
- `src/devops_cli/ci/diagnostics.py` and `src/devops_cli/k8s/port_forward_daemon.py` provide module-level path variables that can be pointed at isolated test files.
- `tests/support/fakes/scanners.py` controls the `PATH` environment variable for scanner tests.
- Symlinks and filesystem paths function consistently on modern Linux containers and GitHub Actions runner environments.

## Existing Tool Considered
The project's hermetic test floor in `tests/conftest.py` and test doubles in `tests/support/fakes/` provide the existing framework for edge enforcement and path isolation without third-party sandboxing tools.

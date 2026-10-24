# Proposal

## Why

Issue #1984: the `binary_sha256` of a Python review tool, such as Bandit or Semgrep, was the SHA-256 of its launcher script. `resolve_tool_version_and_sha` in `src/devops_cli/review/canary.py` hashed the file that `resolve_tool_binary` finds, and for a Python tool that file is the few lines that the installer writes from a console script. The launcher does not change when the package changes, so the record of a tool run did not show which code ran. A launcher also holds the path of its interpreter, so the same package in two environments gave two digests. The issue is the last part of #772.

## What Changes

- When the program of a review tool is a launcher that a console script of an installed distribution wrote, the record names that distribution. The distribution is found in the site-packages directories of the environment whose scripts directory holds the launcher, with the layout of `sysconfig`.
- `binary_sha256` of such a tool is the SHA-256 of the file hashes that the `RECORD` of the distribution lists, sorted by path, less the launcher scripts that the installer wrote from its console scripts. It is `unavailable` when the distribution has no `RECORD`.
- `version` of such a tool is the version of that distribution, so the version and the digest name the same code. Before, the version came from `tools.lock` also when another version ran.
- Each other program, such as a native binary or the Ruff binary that the Ruff distribution ships as a file, keeps the SHA-256 of its file and its version from `tools.lock`.
- `docs/SELF_IMPROVEMENT.md` (Tool Run Records) says what `binary_sha256` covers.
- The record of a tool run is in `profile.json` and in the Tool Runs table of `review.md`, so a consumer sees it, and the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `review-tool-runs`: the record of each run of a review tool, starting with what its binary digest and version name.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/review/canary.py` (`resolve_tool_version_and_sha`). Its callers, `DirectToolExecutor` and `SandboxToolExecutor` in `src/devops_cli/security/tool_executor.py` and `run_tool_canary` in `canary.py`, do not change.
- Documentation: `docs/SELF_IMPROVEMENT.md`.
- Tests: `tests/review/test_review_tool_binary_digest.py`.
- The canary cache key holds the version and the digest, so the canary of a Python tool runs again after the change. It runs one time for each key.

## Feasibility

- Code, at base 90687950: `resolve_tool_version_and_sha` returned `_hash_binary_path(str(binary))`, the SHA-256 of the bytes of the resolved program file.
- Command output on the devcontainer: `bandit` resolves to `.venv/bin/bandit` of the checkout, a console script launcher of 320 bytes in the main checkout and of 349 bytes in a worktree. Each starts with `#!` and the absolute path of the interpreter of its `.venv`. `semgrep` resolves through the link in `~/.local/bin` to the launcher of 379 bytes in the `devops install-tools` environment `<user data root>/tools/semgrep/1.179.0/bin/semgrep`.
- Command output: the `RECORD` files of Bandit 1.9.4 in the two `.venv` directories differ only in the three rows of `../../../bin/bandit`, `bandit-baseline` and `bandit-config-generator`. The two `RECORD` files have different SHA-256 values. Thus a digest of the `RECORD` file alone also changes when only the launchers change.
- Command output: the Ruff and zizmor distributions have no console scripts. Each `RECORD` lists its native binary as `../../../bin/<name>`, of 24 MB and 27 MB. Their programs must keep the digest of the file.
- Lock: `src/devops_cli/tools_lock/semgrep.txt` pins 8 hashes for `semgrep==1.179.0` and `bandit.txt` pins 2 for `bandit==1.9.4`, one for each wheel and the sdist. The installed `.dist-info` has no `direct_url.json` for an install from an index (PEP 610), so it does not say which of the pinned files was installed. The Bandit of the `.venv` comes from `uv.lock`, not from `tools.lock`.
- Library, CPython 3.14.7: `importlib.metadata.Distribution.files` reads `RECORD` into `PackagePath` objects, each with its `hash` (`FileHash`, `mode` and `value`), as the packaging specification "Recording installed projects" (PEP 376, PEP 627) defines the file. `importlib.metadata.distributions(path=...)` searches the given directories, and `entry_points.select(group="console_scripts", name=...)` finds the console script of a launcher. `sysconfig.get_path(<key>, "venv", vars={"base": <prefix>, "platbase": <prefix>})` gives the `purelib`, `platlib` and `scripts` directories of an environment (the `venv` scheme exists since Python 3.11).
- Command output after the change: Bandit in the main `.venv` and in the worktree `.venv` gives the same digest, `c06127d8…`. Semgrep gives `1.179.0` and `e1621c72…`. kube-linter, Pluto, Gitleaks, Ruff and zizmor keep the digest of their file. A lookup takes from 0.01 s (Bandit) to 0.17 s (mypy), one time for each program path.

## Existing Tool Considered

The standard library covers the need. The installer already wrote the SHA-256 of each installed file into `RECORD`, and `importlib.metadata` reads it, with the entry points that tell a launcher from a native binary. `sysconfig` gives the directories of the environment that holds a launcher. The change adds no dependency and hashes no directory tree. No internal code is deleted: the file digest stays for each program that no console script wrote.

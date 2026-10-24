# Design

## Context

A review starts each tool through a `ToolExecutor`, and the record of each run (`ToolRun`) holds `version` and `binary_sha256` from `resolve_tool_version_and_sha`. A Python tool runs from a launcher that its installer writes from a console script: in a virtual environment of `devops install-tools` (Bandit and Semgrep, `tools.lock`), in the `.venv` of the project (Bandit and mypy, dev dependencies), or in another environment such as a `uv tool` environment. The launcher runs the interpreter of the environment whose scripts directory holds it, so the metadata of that environment applies. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The digest of a Python tool changes when a file of its package changes, and stays the same when only its launcher changes.
- The version and the digest name the same installed distribution.
- A native binary keeps the digest of its file.

**Non-Goals:**

- The dependencies of a tool. A tool of `tools.lock` gets them from a hashed requirements file, and a review records the digest of the lock as one of its inputs.
- A check that the files on disk still match `RECORD`. The digest names the distribution as the installer recorded it.

## Decisions

- **The digest is the SHA-256 of the hashed rows of `RECORD`, sorted by path, less the launchers.** Each row gives the path of a file and the hash that the installer wrote. The launchers are the rows whose file name is a console script of the distribution and whose file is in the directory of the launcher. Sorted rows give one digest for any order that an installer writes. Rejected: the SHA-256 of the `RECORD` file. In the two `.venv` directories of this host, the `RECORD` files of Bandit 1.9.4 differ only in the rows of the three launchers, whose shebangs name two interpreters, so the two digests differ for the same package. Rejected: leave out each row outside the import directory (`../`). The Ruff and zizmor distributions ship their binaries there, and a hybrid distribution can ship a binary there beside its console scripts.
- **The distribution is the one whose console script has the name of the launcher, in the environment of the launcher.** The environment is the parent of the scripts directory, and `sysconfig` with the `venv` scheme gives its `purelib` and `platlib` directories. This covers a virtual environment, a `uv tool` or pipx environment, a user base such as `~/.local` and a prefix such as `/usr/local`. Rejected: the distribution named for the tool in the environment of devops-cli (`importlib.metadata.distribution("bandit")`). The Semgrep that runs is in its own environment, not in the environment of devops-cli. Rejected: start the interpreter of the launcher to ask for its metadata. It starts a process for a value that the files give.
- **The digest does not use the hashes that `tools.lock` pins.** `semgrep.txt` pins 8 hashes for `semgrep==1.179.0`, one for each wheel and the sdist, and the installed `.dist-info` has no `direct_url.json` for an install from an index (PEP 610), so it does not say which file was installed. The Bandit of the project `.venv` comes from `uv.lock`, not from `tools.lock`.
- **The version of a Python tool is the version of its distribution.** The record then names one distribution, also when a host has a version that is not the pin. Each other program keeps the version that `tools.lock` pins, else the version of the distribution of that name in the environment of devops-cli.
- **A distribution without `RECORD` gives `unavailable`.** Without hashes, nothing names the package, and the digest of the launcher would name the wrong file. `unavailable` is the value that the record already uses for a digest it cannot get (`CONST_TOOL_DIGEST_UNAVAILABLE`).
- **The rows of the installer metadata stay in the digest.** `INSTALLER`, `REQUESTED` and the bytecode that pip records are rows of `RECORD`. Two installers can thus give two digests for one package: a false difference, never a false match. Rejected: a list of installer files to leave out. Each installer can add files, and the list would need upkeep with no gain in what the digest shows.

## Risks / Trade-offs

- [A launcher whose environment does not have the `sysconfig` layout, such as a Debian `/usr/bin/bandit` with its package in `dist-packages`] → No distribution is found, and the record holds the digest of the launcher file, as before. `devops install-tools` and a project `.venv` have the layout.
- [The result is kept for each program path for the life of the process] → A package that changes in place under a long-running process, such as the MCP server, keeps its old version and digest until the process starts again. `_hash_binary_path` kept the file digest on the same terms, and `devops install-tools` puts each version in a directory of its own.
- [An environment of another Python version than devops-cli] → `sysconfig` gives the `site-packages` of the running version, so no distribution is found and the record holds the digest of the launcher file. `tools.lock` pins Python 3.14 for its environments, and devops-cli needs 3.14.

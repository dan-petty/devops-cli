# review-tool-runs Specification

## Purpose
The record of each run of a review tool names the tool, its version and the digest of the code that ran, so that two reviews show whether the same tools ran.

## Requirements

### Requirement: The binary digest of a Python review tool names its installed distribution
When a console script of an installed distribution wrote the launcher of a review tool, the record of a run SHALL name that distribution, from the site-packages directories that `sysconfig` gives for the environment of the launcher. The `version` SHALL be its version. The `binary_sha256` SHALL be the SHA-256 of the file hashes in its `RECORD`, less the launcher scripts, else `unavailable` when it has no `RECORD`.

#### Scenario: Only the launcher changes
- **WHEN** Bandit is installed again in its environment with the same package files and a launcher that names another interpreter
- **THEN** the `binary_sha256` of Bandit stays the same
- **AND** it is not the SHA-256 of the launcher file

#### Scenario: A file of the package changes
- **WHEN** Bandit is installed again in its environment with one changed file in its package
- **THEN** the `binary_sha256` of Bandit changes and its `version` stays the same

#### Scenario: A Python tool at a version that the lock does not pin
- **WHEN** the Semgrep on PATH is a launcher of the Semgrep distribution at version 1.0.0
- **THEN** the `version` of Semgrep is 1.0.0

#### Scenario: A distribution without a RECORD
- **WHEN** the Bandit on PATH is a launcher of a Bandit distribution that has no `RECORD`
- **THEN** the `binary_sha256` of Bandit is `unavailable`

### Requirement: The binary digest of a native review tool is the digest of its file
When no distribution in those directories has a console script that wrote the program of a review tool, the `binary_sha256` of a run SHALL be the SHA-256 of the program file.

#### Scenario: A native binary
- **WHEN** the kube-linter on PATH is one binary file, and the Ruff on PATH is the binary that the Ruff distribution ships as a file and not as a console script
- **THEN** the `binary_sha256` of each is the SHA-256 of its file
- **AND** the `version` of kube-linter is the version that `tools.lock` pins

### Requirement: A tool run can start from a program that the PATH does not name
A `ToolRequest` SHALL name, in `program`, the absolute path of the program that starts its tool when the PATH of the host does not name it. Each executor SHALL start that program by its path, not by the file that its link leads to. The record of the run SHALL name the tool in `tool`, and the file name of the program as the first element of `argv_template`.

#### Scenario: A request names a program
- **WHEN** a request for a tool names a program that is a copy of the tool, outside the PATH
- **THEN** the program starts, and the record names the tool and starts its `argv_template` with the file name of the program

#### Scenario: A relative program
- **WHEN** a request names a relative path as its program
- **THEN** the request is refused

### Requirement: The record of a program run names the distribution of the tool beside the program
The `version` and the `binary_sha256` of a run that starts from a `program` SHALL name the distribution of the tool in the environment whose scripts directory holds the program. With no such distribution, the `binary_sha256` SHALL be the SHA-256 of the program file, and the `version` SHALL be the pin of `tools.lock`, else `unknown`.

#### Scenario: The interpreter of an environment that holds the tool
- **WHEN** the program is the `python` of a `.venv` that holds mypy 2.3.1, and that `python` is a link to an interpreter outside the `.venv`
- **THEN** the `version` is 2.3.1, and the `binary_sha256` is the one that the mypy launcher of that `.venv` gives
- **AND** it is not the SHA-256 of the interpreter file

#### Scenario: The interpreter of an environment without the tool
- **WHEN** the program is the `python` of a `.venv` that holds no mypy
- **THEN** the `binary_sha256` is the SHA-256 of the interpreter file, and the `version` is `unknown`

### Requirement: A review starts mypy through its tool executor
A review SHALL start mypy through the executor of its other scanners, as `python -I -m mypy`. The `program` SHALL be the interpreter of the `.venv` of the checkout, else the one that runs devops-cli. The request SHALL name the environment of the interpreter as a read-only bind. Mypy SHALL get its cache directory through `MYPY_CACHE_DIR`, so the `argv_template` of its record holds no path.

#### Scenario: The record of the mypy run of a review
- **WHEN** a review of a Python file runs in a tree whose `pyproject.toml` sets the Python version of mypy
- **THEN** the tool runs of the review hold a mypy run
- **AND** its `argv_template` starts with the file name of the interpreter, then `-I -m mypy`, and holds no path

#### Scenario: The request of a mypy scan
- **WHEN** the checkout has a `.venv` with a `python`
- **THEN** the request names that `python` as its program and the `.venv` as a read-only bind, and sets `MYPY_CACHE_DIR` to a directory outside the tree

#### Scenario: A mypy run that times out
- **WHEN** the executor answers that the mypy run ran out of time after 5 s
- **THEN** the mypy scan fails with the reason `timed out after 5 s`

### Requirement: A review runs its canaries on its tool executor and keeps no record of them
A review SHALL run the canary of each tool that it starts on the executor that it was given, once for each tool. The review SHALL keep no record of a canary run among its tool runs. The canary of mypy SHALL name the interpreter that runs devops-cli as the `program` of its request.

#### Scenario: The canaries of a review
- **WHEN** a review that was given an executor runs its static scanners two times on a Python file
- **THEN** the executor got one canary request for Bandit and one for Semgrep
- **AND** the tool runs of the review hold no canary run

#### Scenario: The canary of mypy
- **WHEN** the canary of mypy runs
- **THEN** its request names the interpreter that runs devops-cli as its program, with the arguments `-I -m mypy`

### Requirement: The record of a run names the network of the tool
The record of each run SHALL name, in `network`, the network that the tool had: `host` for the direct executor, `none` for the sandbox executor with no network profile, and the name of the profile, `kube-api`, for the sandbox executor with that profile.

#### Scenario: The network of each kind of run
- **WHEN** the direct executor runs a request, and the sandbox executor runs a request with no network profile and a Popeye request with the profile `kube-api`
- **THEN** the records name the network `host`, `none` and `kube-api`

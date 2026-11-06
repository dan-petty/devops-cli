# Design

## Context

See proposal.md (#3585). Two walks went up to the root of the file system and took any `config.yaml`. The check for a project root ran after the file check in each directory, so a directory without a marker never stopped the walk.

## Decisions

### 1. One walk, accepted at a project root only
- **Decision**: `project_config_directories(start_dir)` yields `start_dir`, then each ancestor that holds `.git` or `.devcontainer`, and ends at the first such ancestor. Both callers use it.
- **Rejected**: stop the walk at the system temporary directory. It hard-codes a host path, and the marker is a property of the project.
- **Rejected**: set HOME or the working directory in the test. The ancestors of `tmp_path` still reach `/tmp`.
- **Rejected**: change into the directory in the SSH test, as the issue design says. The walk starts from the directory that the call gives, not from the working directory, so the failure stays.

### 2. Install-tools status test gets a target directory and a PATH
- **Decision**: pass `--target-dir <empty dir under tmp_path>` and set PATH to an empty directory. Both inputs of the command are then the test's own.
- **Rejected**: PATH alone. The target directory is searched first and holds the devcontainer CLI on a workstation.
- **Rejected**: patch `shutil.which`. PATH already reaches the lookup.

### 3. Popeye case uses a stand-in
- **Decision**: a `popeye` stand-in first on PATH, which writes a marker if it starts. The case asserts that the refusal names `kube-api` and the marker does not exist.
- **Rejected**: expect the missing-tool error. The case holds the refusal of the network profile.

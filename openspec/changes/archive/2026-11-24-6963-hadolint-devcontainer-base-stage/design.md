# Design

## Decisions

### 1. Add inline ignore for DL3066 in the base stage
The `base` stage in `.devcontainer/Dockerfile` switches to user `vscode`.
The base devtools image provides this user.
Hadolint flags non-numeric usernames under rule DL3066.
The `project` stage at line 81 already holds `# hadolint ignore=DL3066`.
The `base` stage requires the same inline ignore comment.

## Rejected alternatives

### 1. Ignore DL3066 globally in .hadolint.yaml
Rejected because the repository owner decision for #6418 restricts `.hadolint.yaml` to rule DL3008 only (`.hadolint.yaml:5`).
Global suppression lowers the linting threshold for other Dockerfiles.

### 2. Switch to numeric user ID
Rejected because devcontainer specifications and tools expect the username `vscode` (`.devcontainer/Dockerfile:82`).
A numeric ID breaks parity with upstream devcontainer conventions.

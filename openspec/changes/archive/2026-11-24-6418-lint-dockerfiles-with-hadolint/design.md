# Design

## Decisions

### 1. Use shenxianpeng/hadolint-pre-commit
The `shenxianpeng/hadolint-pre-commit` hook installs the `hadolint-py` binary wheel in its isolated environment. It requires no container engine or system-level hadolint install on the runner host.

### 2. Ignore DL3008 in .hadolint.yaml
The repository deliberately does not pin apt package versions. Final container stages take Debian security updates through `apt-get upgrade`. `.hadolint.yaml` ignores DL3008 with the recorded owner decision of 2026-11-19.

### 3. Inline ignores in Dockerfiles
Hadolint flags `TIKTOKEN_CACHE_DIR` under DL3064 because the variable contains the word `TOKEN`. The name comes from the external library `tiktoken`. `USER vscode` in `.devcontainer/Dockerfile` is required by devcontainer specifications. Each case uses an inline `# hadolint ignore` directive.

### 4. Gate row integration
The `hadolint` row runs `uv run pre-commit run hadolint --all-files`. It executes in `devops ci` and is covered by the required `Static Analysis` gate job.

## Rejected alternatives

- Upstream `hadolint/hadolint` pre-commit hook: Rejected because it uses `language: system` and fails on stock runners without a pre-installed hadolint binary.
- Pinning apt package versions: Rejected because it conflicts with Debian security updates and repository conventions.
- Renaming `TIKTOKEN_CACHE_DIR`: Rejected because the external library `tiktoken` reads this specific environment variable.

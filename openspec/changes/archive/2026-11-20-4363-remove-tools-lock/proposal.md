# Proposal: #4363

## Why

`devops install-tools` and `src/devops_cli/tools_lock/` made devops-cli a second package manager: each tool version was a copy that custom Renovate managers kept, and product code and tests read the pins. A Renovate bump of a tool then needed an edit under `src/` or `tests/`, and a pin that no longer matched the installed tool failed a correct build: on 2026-11-20 the devcontainer ran Semgrep 1.186.0 while `tools.lock` and `rules.lock` named 1.179.0. The owner decided on 2026-11-20 that one pull request deletes the command, the package and every reader of it (#4363, comment 7047909430), in place of the chain of #4362 and #4388. The devtools image installs the tools. Closes #4363.

## What Changes

- **Delete**: `devops install-tools`, its help, messages and error texts, `docs/commands/install-tools.md`, the package `src/devops_cli/tools_lock`, the install plan of `devcontainer_plans.py`, `CONST_TOOLS_LOCK_REPO_DIR`, `DEFAULT_LOCAL_BIN_DIR`, the `osv-scanner` audit of the lock requirement files with `.osv-scanner-ignore.yaml`, the reader of `tools.lock` and of its requirement files in `devops research`, the release binaries of the watch list, the vendored gh-dash schema and its tests, the lock tests of `tests/tools_lock/`, the installer tests, and the Renovate managers, groups and holds of the lock.
- **Find on PATH**: the review finds `ruff` and `semgrep`, and `devops infra` finds `ansible-runner`, through `require_binary` and `check_binary`. A missing tool raises `DependencyError` with its upstream install page. A missing `ruff` reaches the caller and is no failed model call.
- **Read the installed version**: `k8s doctor` and `deploy-stack` read `kubectl version --client -o json`. The analysis and the knowledge base read the versions that the tool runs recorded; a manual of a tool with no recorded version matches by name and is no drift. A native tool records `unknown` with its binary digest. The review profile hashes the tool runs (`tool_versions_digest`).
- **Infra**: the Ansible environment has no pinned version. A plan record with `ansible_core`, from before this change, does not read: plan again.
- **Alternatives**: the inventory reads `src/devops_cli/config/commands.py`, `src/devops_cli/roadmap/runner_tools.py` and `src/devops_cli/infra/ansible_facts.py`, which name, with no version, the programs that devops-cli or a Job starts, in place of `tools.lock`.
- **Kept**: `tests/tools_lock/test_k8s_argo_workflows.py` reads no pin and holds safety rules of the Argo Workflows manifests, so it moves unchanged to `tests/k8s/`.
- **Image scan**: the third-party image scan also scans the cluster cloudflared image, in place of the tag floor test.
- **Workflows**: the Service Image Tests workflow drops the `src/devops_cli/tools_lock/**` path filter. #6543 moved every other workflow from `devops install-tools` to the commands of the devtools image.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- Removed: `tools-lock-install`, `tflint-release-pin`, `release-download-retries`.
- Modified: `infra-onboard`, `infra-plan`, `k8s-doctor`, `k8s-helm-deploy`, `review-tool-runs`, `ai-review-profile`, `ai-retrieval-gold-set`, `scanner-adapters`, `research-advisories`, `research-inventory`, `review-tool-databases`, `ci-dependency-audit`, `ci-fail-to-pass`, `command-dry-run-class`, `docs-ste-style`, `github-session-timeouts`, `cloudflared-release-pin`, `crawl4ai-service`, `release-concurrency-and-renovate`, `ci-service-image-tests`, `devcontainer-image-tools`, `ci-devcontainer-image`, `container-image-layers`, `subprocess-environment`.

## Impact

- Users: `devops install-tools` exits with `No such command`. A host that is no devtools image installs each tool with its own installer, or runs `mise install` with the `mise.toml` of the devtools repository. A tool only in `~/.local/bin` and not on PATH is not found.
- Records: a review record of a native tool names `unknown` as its version, and `profile.json` holds `tool_versions_digest`. An infra plan record from before this change must be planned again.
- Renovate: a bump of a tool of the devtools image needs no edit under `src/` or `tests/`.

## Feasibility

- `git grep -lE 'install-tools|install_tools|tools_lock|tools\.lock'` named 157 files on 2026-11-20. After the change the proof grep of the issue still names records that stay as history: the recorded eval and census fixtures under `tests/fixtures/roadmap*`, an intake eval case, a historical title of #5107 in a title test, and the ADRs.
- `kubectl version --client -o json` prints `clientVersion.gitVersion`; `semgrep --version` printed `1.186.0` in the devcontainer, and `devops review rules test --check` passed with it.

## Existing Tool Considered

The devtools image (dan-petty/devtools) installs the tools with apt and mise, and `mise.lock` holds the checksum of each platform. `shutil.which` (through `require_binary`) finds a tool, and the tool states its own version. The change deletes code and writes no new installer or version reader.

# Proposal: #4388

## Why

Product code reads tool versions from `tools.lock`, which is a copy of the pins. A Renovate bump of a tool then needs an edit under `src/` or `tests/`, and the code reports the pin and not the tool that runs: on 2026-11-20 the devcontainer ran Semgrep 1.186.0 while `tools.lock` and `rules.lock` named 1.179.0, so `devops review rules test --check` failed on a correct rule pack. The owner decided on 2026-11-19 that the devtools image installs the tools, so the installed tool is the one source of its version. Closes #4388.

## What Changes

- `path_version` and `version_line` move from `devops_cli.tools_lock.versions` to `devops_cli.core.binaries`.
- `devops k8s doctor` and `devops k8s deploy-stack` take the kubectl version of the skew rule from `kubectl version --client -o json`. The doctor snapshot holds it.
- The review analysis takes the version of a tool from the record of its run, and the Python version from the running interpreter. The knowledge base matches a tool manual against these versions. The canary and the tool executor record the version of the installed distribution, else `unknown` with the digest of the binary.
- The review profile holds `tool_versions_digest`, the digest of the version and the binary digest of each tool that ran, in place of `tools_lock_digest`.
- `rules.lock` holds no `semgrep_version`, and its model refuses the field. `devops review rules test` prints the version that `semgrep --version` states. A change of `tools.lock` or `semgrep.txt` runs the rule pack workflow.
- The alternatives check reads no `tools.lock`.
- The OpenSpec contract test replays each recorded scenario with the installed `openspec` in a live test, and compares no pin. The Renovate OpenSpec rule asks for no new recording.
- Tests that compared a pin of `tools.lock` change: the kubectl skew, the kubeconform recording, the scanner registry, the tool executor contract, the binary digest and the rule pack. The test that every scanner program is a command of `tools.lock` goes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-doctor`: the skew rule reads the installed kubectl.
- `k8s-helm-deploy`: the skew warning reads the installed kubectl.
- `review-tool-runs`: a native tool records `unknown` and no pin; the rules lock holds no Semgrep version.
- `ai-review-profile`: the profile hashes the versions of the tools that ran.
- `scanner-adapters`: the requirement that each scanner program is a command of `tools.lock` goes.

## Impact

- Code: `core/binaries.py`, `k8s/doctor.py`, `commands/k8s/stack_lifecycle.py`, `review/analysis.py`, `review/canary.py`, `ai/kb.py`, `ai/review/profile.py`, `review/rules_pack.py`, `commands/review.py`, `config/defaults.py`, `config/constants.py`, and the imports of `commands/install_tools.py` and `openspec/gate.py`.
- Files: `src/devops_cli/review/rules/rules.lock`, `.github/workflows/rule-pack.yml`, `.github/renovate.json`, two task prompts and two knowledge base articles.
- Records: a review record of a native tool holds `unknown` as its version. A `profile.json` holds `tool_versions_digest`. An old profile still loads.
- `devops k8s doctor` and `deploy-stack` start `kubectl version --client`, a local read.

## Feasibility

- `kubectl version --client -o json` prints `clientVersion.gitVersion` (Kubernetes documentation).
- `semgrep --version` printed `1.186.0` in the devcontainer on 2026-11-20, and `devops review rules test --check` passed with this change.
- `git grep -nE 'load_tools_lock|tools_lock_digest|read_tools_lock' -- src` after this change names `tools_lock`, `commands/install_tools.py`, `commands/ci.py`, `devcontainer/devcontainer_plans.py`, `openspec/gate.py` (#6409 owns it) and `research/tool_pins.py`.

## Existing Tool Considered

The installed tools state their versions: `kubectl version --client -o json`, `semgrep --version`, and `importlib.metadata` for an installed Python distribution. The change uses these and writes no new version reader.

# Proposal: #6416

## Why

Issue #6416: CI jobs install their tools with `uv run devops install-tools` before they run, from the release URLs of `tools.lock`. The owner decided on 2026-11-19 that the tools come from the devtools image `ghcr.io/dan-petty/devtools`, and that devops-cli is not a package manager. #4363 deletes the command and `src/devops_cli/tools_lock/`, so no workflow can call the command after this change.

## What Changes

- The new stage `devtools-bin` of `.devcontainer/Dockerfile` holds only the single-file commands of the devtools image that the CI jobs on the runner host run. The new composite action `.github/actions/devtools-commands` restores the commands that a job names from an `actions/cache` entry. The key of the entry names the runner, the digest of the image in the `FROM` line of `.devcontainer/Dockerfile` and the sorted commands. Only on a miss does the action build the stage with the Docker Engine of the runner, which pulls the whole image. The action puts the directory of the commands first on `PATH`, and names no version. These jobs call it in place of their `install-tools` steps:
  - `Static Analysis` (tofu, osv-scanner, trivy, kube-linter): its `bwrap` row needs the sandbox of the host.
  - The test shards (promtool): the coverage data of a shard names the paths of its checkout, and `Tests & Coverage` joins the data on the host.
  - `Copilot Setup Steps` (gitleaks, osv-scanner, tuicr): GitHub ignores a `container` key of this job.
  - `Service Image Tests` (promtool, kubectl): the job loads and runs the Service image with the Docker Engine. The step copies the two commands to the tools directory that it mounts in the image.
  - `Image Pins` (kubectl, helm): a container job pulls the whole image on each run, 40 s in the first run of this change.
- `Rule Pack Tests` runs in the devtools image (`container.image` with the tag and the digest of the Dockerfiles): the Semgrep of the image is a venv that runs only with the Python of the image. The Copilot agent gets no Semgrep for the same reason.
- The Semgrep pin of the rule pack goes, because Semgrep now comes from the image: `RuleLockEntry.semgrep_version`, the field in `rules.lock`, `pinned_semgrep_version` and the compare of `--check`. The command prints the version that the installed `semgrep --version` states. The help text of `--check` names no pinned version. This part is the reviewed rule pack part of the branch of #4388.
- The `paths` filters of `copilot-setup-steps.yml`, `image-pins.yml` and `service-image-test.yml` add `.devcontainer/Dockerfile` and `.github/actions/devtools-commands/**`. `rule-pack.yml` names the image, so the pull request of a new image changes it and runs it.
- Tests: the copilot run lines of `tests/invariants/test_workflow_contracts.py` lose the four tool lines, `tests/commands/test_ci.py` loses the trivy step order test and the allowlist entries of the removed steps, `tests/roadmap/test_roadmap_runner_tools.py` reads the `commands` of the action as tools of the required jobs, and `tests/commands/test_review_rules_pack.py` uses a stand-in Semgrep version and no pin.
- `docs/SDLC.md` names the source of the tools of a CI job, the kubectl and helm of the image pins job and the paths of the Service Image Tests. `docs/CLUSTER.md` names the promtool of the devtools image.
- The specs `devcontainer-image-tools`, `ci-service-image-tests` and `k8s-image-pins` name the `install-tools` step, the pinned helm and the old path lists, so the delta changes those requirements. `review-tool-runs` gets the requirement of the rules lock with no Semgrep version.

The OpenSpec and Style Dictionary steps install from the root `package-lock.json` with `npm ci` (#6409). Their `echo "$HOME/.local/bin" >> "$GITHUB_PATH"` line served only the `install-tools` lines, so it goes. After this change, no workflow runs `devops install-tools`.

The change fits one pull request.

## Capabilities

### Modified Capabilities

- `devcontainer-image-tools`: `Static Analysis` takes OpenTofu from the devtools image.
- `ci-service-image-tests`: the paths of the workflow add the stage and the action that give the test tools.
- `k8s-image-pins`: the job takes kubectl and helm from the devtools image, and its paths add the stage and the action.
- `review-tool-runs`: the rules lock holds no Semgrep version.

## Impact

- `.devcontainer/Dockerfile` (stage `devtools-bin`), `.github/actions/devtools-commands/action.yml` (new), `.github/workflows/ci.yml`, `copilot-setup-steps.yml`, `image-pins.yml`, `rule-pack.yml`, `service-image-test.yml`.
- `src/devops_cli/review/rules_pack.py`, `src/devops_cli/review/rules/rules.lock`, `src/devops_cli/commands/review.py`, `src/devops_cli/lang/en/help.py` and the generated pages `docs/commands/review.md` and `docs/commands/ai.md`.
- A host job pulls the devtools image (1796 MB compressed for linux/amd64) only on a cache miss: once for each digest and list of commands, then again when GitHub evicts the entry. The cache holds one entry for each list of commands.
- `devops review rules test --check` passes with any Semgrep on `PATH` whose `--test` passes.

## Feasibility

Read on 2026-11-20 against `origin/main` at `1b52008a7` and `0d14844d2`, with skopeo, Podman 5.8.6 and the devtools image `20261119@sha256:a7b2f111…`.

- `skopeo inspect --no-creds` reads the image with no credentials. The linux/amd64 image has no `User`, so a container job runs as root, and its 10 layers are 1796 MB compressed.
- In the image, `/usr/local/bin` holds tofu, osv-scanner, trivy, kube-linter, promtool, gitleaks, helm and kubectl as static executables (`ldd`: not a dynamic executable) and tuicr linked to glibc. `semgrep` is a link to `/usr/local/lib/devtools/semgrep/bin/semgrep`, a venv whose `python` is `/usr/bin/python3.14` of the image.
- The GitHub document "Customizing the development environment for Copilot coding agent" lists the keys that the `copilot-setup-steps` job can set: `steps`, `permissions`, `runs-on`, `services`, `snapshot` and `timeout-minutes`. GitHub ignores every other key, `container` too.
- `docs/SDLC.md` says that the `bwrap` row runs in `Static Analysis` on its GitHub-hosted runner. The default seccomp profile of Docker refuses the namespaces that bubblewrap makes, so in a container job the row skips.
- The `test` job reads `.data/shards/*/.coverage` on the host, and the data of a container job names `/__w/...` paths.
- The first CI runs of this change built the stage in each host job: 35 s to 61 s for the step, of which the pull of the image took 21 s to 26 s, against 6 s to 10 s for the old `install-tools` steps. `Initialize containers` took 52 s in `Rule Pack Tests` and 40 s in `Image Pins`. The PR head took 424 s for the slowest shard and the join of `Tests & Coverage`, over the 360 s of AGENTS.md rule 5 (P0 #6262).
- In the devtools image, `devops review rules test --check` failed on `semgrep_version '1.179.0' != pinned '1.186.0'` before the pin went, and passes with Semgrep 1.186.0 after it.
- `docker buildx build --file .devcontainer/Dockerfile --target devtools-bin --output type=local,dest=<dir> .` writes the nine commands. The key step of the action reads the digest of the `FROM` line and fails with an error that names `.devcontainer/Dockerfile` when no line names the image by tag and digest. A name that the stage does not hold fails the build step.

## Existing Tool Considered

The devtools image holds every tool, and the GitHub Actions `container` key runs a job in it. For a job that cannot run in it, a BuildKit stage of the Dockerfile that already pins the image gives the commands, as the `devcontainers-cli` stage gives the Dev Containers CLI to `.github/actions/devcontainer-image`, and `actions/cache` keeps them between runs. Maintained setup actions exist for OpenTofu (`opentofu/setup-opentofu`) and Trivy (`aquasecurity/setup-trivy`), but none installs promtool, osv-scanner, kube-linter, gitleaks or tuicr, and each one adds a version pin apart from the image. The change builds no installer. It deletes 13 `install-tools` lines of five workflows, with four whole steps, the trivy step order test, three allowlist entries, `pinned_semgrep_version` and the Semgrep version of `rules.lock`.

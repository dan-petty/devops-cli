# Proposal: #4361

## Why
The root `Dockerfile` installs tools itself (#4361): a gh download with a URL and a checksum, the actionlint image stage, the `runner-tools` stage, and `devops install-tools` runs for OpenSpec, promtool, Trivy, OpenTofu, kubectl and helm. A change of `src/` runs some of these steps again, and each tool version is a copy that a person or a custom Renovate manager keeps. Owner decisions of 2026-11-19: devops-cli is not a package manager, and the runner image builds FROM the devtools image (`ghcr.io/dan-petty/devtools`), which Renovate moves by digest. The Service and MCP server images stay on `python:3.14-slim-trixie` with the full Trivy gate.

## What Changes
- Stage `devtools` names `ghcr.io/dan-petty/devtools` by tag and digest: the image of `.devcontainer/Dockerfile`. The runner uses the OpenSpec of that image; the OpenSpec pin of the project reaches a runner Job through the coder bootstrap (#6517) after #6409. Stage `runner-deps` builds FROM it, adds the user `devops` (uid 1000) and the venv of the runtime and the dev requirements of `uv.lock`, through bind mounts of the `lock` stage and a uv cache mount. Stage `runner-builder` installs the project, and stage `runner` copies only the project into one `COPY --link` layer. `UV_PYTHON` names the Python of the devtools image. The runner runs no `apt-get upgrade` of its own: the devtools image runs it in its own build, and Renovate moves the runner to a new devtools image each week.
- The gh download, the actionlint stage, the `runner-tools` stage, each `devops install-tools` run and the `runner_tools` build step leave the `Dockerfile`.
- The MCP server image builds on `service-deps` (`python:3.14-slim-trixie`) and not on `runner`. It copies kubectl and helm from the devtools image, and it holds gh, git and OpenSpec as the Service image does.
- The Service image copies gh from the devtools image. Stage `openspec` keeps OpenSpec and only the npm packages that it needs from the npm tree of the devtools image (`npm prune --offline`), and the official Node binary runs it.
- The smoke tests of `ci.yml` and `release.yml` run `kubectl version --client` and `helm version` in the MCP server image, and `python -m devops_cli.roadmap.runner_tools` with no tool path in the runner image. The runner size bound becomes 7000000000 bytes (6.38 GB measured). The runner scan reports with exit code 0; the Service and MCP server scans keep exit code 1.
- `RUNNER_TOOLS` names the devtools image as the source of each tool that is not a dev dependency or the project, and it holds kubectl, kube-linter, osv-scanner, npm, zsh and ps, which the image now gives and which a source of the gate needs. `NOT_IN_RUNNER` names only programs that a step of the Job does not count on.
- `.trivyignore.yaml`: the kubectl entries take the new path `usr/local/bin/kubectl` for the MCP server gate. The entries of tofu, promtool, Trivy and actionlint go, because only the report-only runner scan reads them.
- SECURITY.md gets the table of the controls that change for a dedicated development resource or a sandbox, with the two entries that the owner approved on 2026-11-19 (#5447). The rows state the real exposure of the Job pod: it loads every key of the Secret `devops-cli`, and #6518 narrows them.
- Renovate: the devtools group sets the prefix `fix(deps):`. The OpenSpec rule stays as on `main`. The descriptions of the base image, uv, node and actionlint rules name the new form.
- Tests that read Dockerfile values that this change removes go (owner rule of 2026-11-16): the gh floor tests, the kubectl and helm floor test, and the stage and layer tests of the runner, MCP server and dependency stages.

This changes the images that the cluster runs and the source table of the runner tools, so it carries spec deltas. It fits one pull request.

## Capabilities
- `container-image-layers`: modified (dependency layers, final stages) and added (tools from the devtools image).
- `mcp-server-image`: modified (base, cluster tools, user).
- `roadmap-implement-runner`: modified (runner stage, interpreter, build leftovers, hooks, tool check, smoke test, tool table); the scan requirement becomes report-only.
- `ci-image-scan`: modified (exit code of the runner scan).
- `release-concurrency-and-renovate`: modified (the `devtools` group holds the devtools image of both Dockerfiles).
- `roadmap-service-deployment`: modified (OpenSpec of the Service image from the devtools image).
- `devcontainer-image-tools`: modified (the runner takes OpenTofu from the devtools image).

## Impact
- The runner image grows from 2.42 GB to 6.38 GB (Podman, local build), because the devtools image holds about 30 more tools. The first pull on a node takes 1.8 GB of compressed devtools layers once for each devtools digest.
- The MCP server image shrinks from 2.98 GB to 1.68 GB; the Service image stays at 1.55 GB.
- A change of `src/` builds one new layer of 35 MB in each image.
- The runner holds the review scanners, kube-linter and kubectl, so #6263, #5394 and #3562 can close after the merge.
- `devops install-tools` and `tools.lock` stay in `src/`; #4363 removes them.

## Feasibility
- `skopeo inspect` of `ghcr.io/dan-petty/devtools:20261120` gives the multi-arch index `sha256:dc4ee4386d1b98116db489f4f507afc7236dcb04e97385eab378a48491cbf9b0`. `docker run` of that image showed the paths that this change reads: `/usr/local/bin/{gh,kubectl,helm,actionlint,promtool,trivy,tofu,uv,kube-linter,osv-scanner}`, `/usr/bin/{python3.14,node,npm,git,curl,jq,shellcheck,zsh,ps,bwrap}`, and OpenSpec under `/usr/local/lib/devtools/npm/node_modules/@fission-ai/openspec`. Versions: gh 2.105.0, kubectl 1.37.2, helm 4.3.2, OpenSpec 2.1.1, Node 24.22.3, uv 0.13.9, Python 3.14.10, glibc 2.43. The image has no user with uid 1000.
- `docker run` of `ghcr.io/dan-petty/devtools@sha256:a7b2f111941beaf5d36efb19f6ed2a50f8bed3062003498b97523da926143c51`, the digest of `.devcontainer/Dockerfile`, printed OpenSpec 2.1.0, the version of `tools.lock`, and the same paths and versions of the other tools.
- With OpenSpec 2.1.1, `openspec validate --all --strict` fails three active plans on the length of a MODIFIED requirement, so this change does not move `tools.lock` to 2.1.1 (design.md).
- `npm prune --offline --ignore-scripts` in a copy of the npm tree, with only OpenSpec in `package.json`, removed 110 packages, left 23 MB, and `openspec --version` printed 2.1.1 with no network.
- Local builds with Podman 5.8.6 of `--target runner`, `mcp-server` and the Service image passed, and every smoke command of `ci.yml` passed on them under `set -euo pipefail`. Trivy 0.76.2 with the flags of the action: MCP server and Service exit 0 with no finding; the runner holds 286 findings (4 CRITICAL) in 15 devtools binaries and the semgrep venv of the devtools image, none in `/app/.venv`.

## Existing Tool Considered
The devtools image (dan-petty/devtools, MIT) gives every tool, and Renovate's `dockerfile` manager moves its digest. npm's own `npm prune` takes OpenSpec and its packages out of the shared npm tree. jdx/mise covers pins and installs at build time, but it gives no prebuilt image and no layer cache, so the devtools image builds with it instead. This change builds no tool of its own. It deletes the gh download block, the actionlint and `runner-tools` stages, five `devops install-tools` runs, the `runner_tools` build step and the tests that read those Dockerfile lines.

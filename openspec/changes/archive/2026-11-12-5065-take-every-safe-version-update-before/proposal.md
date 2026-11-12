# Proposal: #5065

## Why

The owner asked on 2026-11-12 for one pull request with every known version update that is safe now, "so that renovate doesn't create a flood of issues when it is configured". On 2026-11-11 most pin classes were behind (#4893): 53 of 101 Python direct dependencies, 16 of 20 Argo CD charts, 11 of 20 tools-lock binaries, and more. When Renovate (#4905) starts from a current baseline, it opens only the held items and the migrations.

Closes #5065.

## What Changes

GitHub Actions, workflow images and pre-commit:

- astral-sh/setup-uv v10.0.1 and v10.2.0 -> v10.3.3; docker/login-action v4.6.0 -> v4.8.0; github/codeql-action v4.38.2 -> v4.39.3; amannn/action-semantic-pull-request v6.1.1 -> v6.1.2. The version comments of build-push-action (v7.4.0) and setup-buildx-action (v4.4.1) name the tag of their commit.
- The trivy-action version inputs 0.75.0 -> 0.76.2; kjanat/actionlint 1.17.0 -> 1.17.1 (digest); registry:3 new digest.
- pre-commit-hooks v5.0.0 -> v6.0.0; ruff-pre-commit v0.16.8 -> v0.17.4.

Dockerfiles and devcontainer:

- uv 0.13.6 -> 0.13.7 (image, setup-uv inputs, runner tools table); gh 2.102.1 -> 2.103.3; python:3.14-slim-trixie digest (Python 3.14.8 -> 3.14.10); node:24-trixie-slim digest (24.22.2 -> 24.22.3); debian:sid and the dockerfile syntax image pinned by digest.
- Devcontainer features in their major: common-utils 2.5.9 -> 2.7.1, kubectl-helm-minikube 1.3.1 -> 1.3.2, copilot-cli 1.1.3 -> 1.1.4, github-cli 1.1.0 -> 1.1.3, node 2.1.0 -> 2.1.2.

Tools lock:

- trivy 0.75.0 -> 0.76.2, argo 4.1.5 -> 4.1.6, argocd 3.5.4 -> 3.6.1, cloudflared 2026.10.4 -> 2026.11.0, kubectl-argo-rollouts 1.10.0 -> 1.10.2, tuicr 0.27.0 -> 0.28.0, promtool 3.15.1 -> 3.16.0, golangci-lint 1.64.6 -> 1.64.8; each sha256 equals the release asset digest.
- devcontainers-cli 0.89.0 -> 0.90.0; OpenSpec 1.14.3 -> 1.17.0 with its 12 generated skills and its recorded runs; the npm locks take the newest dependencies in range (Style Dictionary: prettier 3.10.1).

Cluster (Argo CD rolls these on merge):

- Charts: argo-cd 10.9.6 -> 10.18.0 (Argo CD v3.6.1), argo-workflows 2.0.13 -> 2.0.18 (v4.1.6), argocd-image-updater 1.3.1 -> 1.4.2, grafana 14.0.1 -> 14.4.1 (Grafana 13.3.1), k8s-monitoring 4.5.2 -> 4.6.0, loki 20.0.2 -> 21.2.1 (Loki 3.7.9 stays), opentelemetry-collector 0.175.0 -> 0.178.3, plugin-barman-cloud 0.8.1 -> 0.9.0, prometheus-operator-crds 32.0.1 -> 33.0.2, prometheus 29.35.0 -> 29.47.2, pyroscope 2.3.1 -> 2.4.3, qdrant 1.19.1 -> 1.20.0, tempo 3.1.0 -> 3.2.1, traefik 42.1.3 -> 42.3.2, open-webui 16.6.0 -> 18.3.0 (image stays v0.11.4).
- Grafana plugins: lokiexplore, metricsdrilldown and pyroscope 3.0.0 -> 3.1.0; exploretraces 3.0.0 -> 3.2.0.
- Images: cloudflared 2026.11.0, LiteLLM v1.103.10 -> v1.103.11, portkey 1.15.0 -> 1.15.2, redis_exporter v1.93.0 -> v1.97.0, valkey 9.1.2 -> 9.1.3, PostgreSQL 17.2 -> 17.11, Mattermost 11.7.11 -> 11.7.15.

Python (`pyproject.toml`, `uv.lock`: 52 direct and 64 transitive moves):

- Main: click 8.5.1, typer 0.28.0, pydantic 2.14.3, pydantic-core 2.50.4, httpx2 and httpcore2 2.16.0, anyio 4.16.0, fastmcp 4.1.8, qdrant-client 1.20.0, pydantic-settings 2.16.2, json-repair 0.64.9, tldextract 5.4.0, python-hcl2 8.2.0, platformdirs 4.14.5, fastapi 0.162.5, uvicorn 0.54.0, logfire 5.6.0, openai 3.49.0, anthropic 1.17.0, opentelemetry 1.45.2 and 0.66b2, dnspython 2.9.2, genai-prices 0.2.3, tree-sitter-markdown 0.5.4, markdown-it-py 4.3.0, graphql-core 3.3.2, cachetools 8.0.0, filelock 4.2.10.
- Dev: pytest 9.2.0, pytest-asyncio 1.4.1.post1, pytest-mock 3.17.0, pytest-randomly 5.1.0, ruff 0.17.4, mypy 2.4.1, ty 0.0.101, diff-cover 11.0.1, zizmor 1.32.0, pre-commit 4.7.0, hypothesis 6.170.15, mutmut 3.8.1, syrupy 7.0.0, ast-grep-cli 0.51.2, time-machine 3.6.0, mdit-py-plugins 0.7.0, lizard 1.26.0, cel-expr-python 0.1.4, type stubs; hatchling >=1.33.0.
- Code fixes that the new versions find: ruff RUF071, the ty rule names, pytest 9.2 `PluginImportFailure`, and the knowledge-base versions.
- `.github/renovate.json` holds google-genai below 3 until the pydantic-ai move (#5098). tenacity 9.2 cannot resolve while google-genai caps it below 9.2.0.

Tests read the pins of the tools lock, the record and the digest form, so the next update of these pins changes no test.

Held, and their issues under #4893:

- Python 3.15 and Node 26: held for a Dependency Dashboard approval.
- golangci-lint 2 #5072, docker-in-docker 4 #5073, azurerm 5 #5074, google 8 #5075, aws 6 with kubernetes 3 and helm 3 (no check validates `tf/`) #5076, OpenSpec 2.0.0 #5078, semgrep 1.185.0, osv-scanner 2.7.1, pluto 5.24.5 and tflint 0.66.0 (no record route inside pytest) #5083.
- dcgm-exporter 4.9.0 #5085, Open WebUI v0.13.3 #5086, Gitea 28 #5087, Mattermost 11.11 or 12 #5088, LiteLLM v1.109 #5091, gpu-feature-discovery v0.20.1 #5092, SearXNG 2026.11.12 #5093, PostgreSQL 18 #5094.
- kubernetes 37 #5095, anthropic 2 #5096, typer 0.29 #5097, pydantic-ai 2.68 with pydantic-ai-harness 0.68 #5098.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change moves pins. tflint stays at 0.65.0, so the `tflint-release-pin` spec does not change.

## Impact

- After the merge, Argo CD syncs the cluster changes: the Argo CD and Grafana pods restart once; Argo CD 3.6 computes the ServerSideApply diff through the API server; Tempo applies the 168 h retention to old traces; Alloy drops every capability except NET_BIND_SERVICE (check `alloy-logs` after the sync); both PostgreSQL databases restart once (17.11); LiteLLM builds its spend-log indexes once at start. Rollback is a revert of the pull request.
- A devcontainer that runs the old image has OpenSpec 1.14.3 in `/usr/local/bin`. Until the image is built again, `uv run devops install-tools --tool openspec` puts 1.17.0 first on PATH; else `devops openspec check` reports drift in the 12 `generatedBy` lines.
- The Service and runner images take the new bases and tools at the next release.

## Feasibility

Read and run on 2026-11-12, against origin/main and the live cluster (read-only):

- Each version came from the registry, release or tag API; each binary sha256 from a download that was hashed and never run, equal to the release asset digest; each image digest from the registry manifest. The issues of the held items hold their evidence.
- Every Argo CD Application was Synced, and each from-value equals the live value. All charts render at the new version with the repository values (`helm template`, kube-version 1.37.2); the three chart majors render the same objects; kubeconform shows no new invalid object; `devops k8s image-pins` resolves all 39 images.
- `uv lock --check` passes; mypy strict and ty pass; the full suite passed on the Python changes (23,696 tests); the static gate rows, `devops openspec check` and the tests that read each pin pass on this branch.

## Existing Tool Considered

Renovate (#4893) makes these updates when it runs. This change uses its managers' view of the pins and takes them once by hand, so the first runs start from a current baseline. No code is built beyond small test changes that read a pin.

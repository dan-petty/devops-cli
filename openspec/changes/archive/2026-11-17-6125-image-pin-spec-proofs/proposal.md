# Proposal: #6125

## Why
The scenarios of the specs of the images, the release pins and the devcontainer say "a test reads <file>": a manifest, `tools.lock`, a `Dockerfile` or `devcontainer.json`. The owner rule of 2026-11-16 (#6060) removes each test that asserts a value of a manifest or a config file, and #6075 deleted many of them. The stage and refine jobs read the living specs and copy their form. #6080 changed the rule for a new scenario: a scenario of a manifest, a workflow or a config file names a validator command or a live check as its proof. A spec also restates a chart version that Renovate has already changed: `loki-release-pin` says 20.0.2, and the Application installs 21.2.3. This change rewrites the scenarios of the second area in the form of #6080. Closes #6125, the sub-issue of this area. Part of #6083: more areas follow, one sub-issue for each area.

## What Changes
- In 7 capabilities, each scenario that read a file now names one of these proofs. #6124 (#6119) already gave `ollama-release-pin`, `ollama-image-pin` and `traefik-release-pin` a `kubectl get` live check, so this change keeps their scenarios:
  - a validator: `uv run devops k8s image-pins`, `uv run devops devcontainer validate`;
  - the dry run of a devops command: `uv run devops k8s deploy-stack --dry-run` or `uv run devops install-tools --tool <tool> --dry-run`;
  - an install: `uv run devops install-tools --tool <tool> --target-dir <dir>`, then the version that the tool prints;
  - a live check of the cluster with `kubectl get` only: the Application status, the image tag of pod `loki-0` compared with the floor and the `appVersion` of `helm show chart`, and the image tag and `imageID` of the cloudflared pods. No scenario enters a pod: the project forbids `kubectl exec` for agents;
  - an image build: the `DevContainer Image` check and its smoke action, `docker buildx build`, `docker image inspect`, `docker history` and `dpkg-query` in a container of the image;
  - a live check of the workspace container: `cat /sys/fs/cgroup/pids.max`, `nvidia-smi -L`, `/proc/sys/net/ipv4/ping_group_range`, `ping`, `findmnt` and `printenv`.
- A requirement that only restates a file goes: a key that the Loki values must not hold, and the deployment mode and its comment of the Loki values. The guard that asked for a test of `--pids-limit` also goes, because #6075 deleted that test (3 requirements).
- A requirement whose scenario name or steps can only describe a read of the file goes out as REMOVED and comes back as ADDED under a new name with the same rule, because OpenSpec keeps each scenario name of a MODIFIED requirement (5 requirements). The new text of the tflint pin drops the version that each bump changes.
- The text of the Loki pin and of the OpenTofu pin drops the exact version. The Loki pin keeps the floor of the release that fixes CVE-2026-21729.
- No code and no test changes.

## Capabilities
- `loki-release-pin`: 3 modified, 2 removed.
- `cloudflared-release-pin`: 2 modified.
- `tflint-release-pin`: 1 removed and added again.
- `container-image-layers`: 3 removed and added again.
- `devcontainer-image-tools`: 5 modified, 1 removed and added again.
- `devcontainer-process-limit`: 1 modified, 1 removed.
- `devcontainer-workspace-image`: 3 modified.

## Impact
- Census `git grep -c -i "a test reads" -- openspec/specs`, on `main` after #6120 and #6124: the 7 capabilities fall from 18 hits to 0, and all specs fall from 209 to 191. Before #6124, the area of 10 capabilities had 22 hits; #6124 removed the 4 hits of `ollama-release-pin`, `ollama-image-pin` and `traefik-release-pin`.
- No user, command or service changes. The stage and refine jobs read the new scenarios as examples of the proof form.

## Feasibility
- Each command that a scenario names exists: `devops k8s image-pins`, `devops devcontainer validate` and `init`, `devops k8s deploy-stack --dry-run`, `devops install-tools --dry-run`, `--target-dir` and `status`.
- The dry run of `deploy-stack --stack logging` installs `grafana-community/loki` at the `targetRevision` of Application `loki`.
- On the cluster, `kubectl get` shows that pod `loki-0` runs `grafana/loki:3.7.10`, the `appVersion` of chart 21.2.3. The cloudflared pods run `cloudflare/cloudflared:2026.11.0` with one digest. Application `loki` is `Synced` and `Healthy`, its `helm` block holds only the values file, and namespace `logging` holds no ServiceAccount `loki-memcached`.
- `install-tools --tool tflint --dry-run` requests the `.zip` of the release `v<version>` of the lock.
- In the workspace container, `pids.max` is 8192, `nvidia-smi -L` lists the GPU, the ping range is `1000 1000`, `findmnt` shows the four data mounts and no cache mount, and `UV_CACHE_DIR` is not set. The tools of the image are under `/usr/local/bin`, with the files of the Python and Node tools under `/usr/local/share/devops-tools/`.
- #4550 measured the layers of the runner and Service images with `docker image inspect` and `docker history`, the method that the scenarios of `container-image-layers` name.

## Existing Tool Considered
- OpenSpec deltas and `openspec archive` apply the rewrite. The proofs are the tools that the repository and the cluster already run: `devops k8s image-pins`, `devops install-tools`, Helm, kubectl, Argo CD, BuildKit, the Dev Containers CLI and the smoke action. No new tool. Cost: about 1M agent tokens and 2 hours.

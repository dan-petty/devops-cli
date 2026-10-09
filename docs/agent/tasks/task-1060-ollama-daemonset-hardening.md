# Task: The Ollama Tier DaemonSets Run as Non-Root, With No Privilege Escalation or Capabilities, RuntimeDefault Seccomp and a Read-Only Root Filesystem (#1060)

**Issue**: [#1060](https://github.com/dan-petty/devops-cli/issues/1060)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: scope/k8s, scope/security

## Description
None of the 9 ollama tier DaemonSets in `k8s/llm/profiles/ollama-profiles.yaml` set a pod or container `securityContext`. ollama ran as root with the default capabilities, privilege escalation allowed, no seccomp profile and a writable root filesystem. It wrote to the hostPath `/var/lib/ollama`, mounted at `/root/.ollama`. The llm stack's first-party workloads (gateway, portkey, valkey, cloudflared, jaeger) already ran as non-root.

The live cluster, read with `kubectl get` and `kubectl describe` only, matched the manifest:
- Four tiers are scheduled and Ready: 16gib, 48gib, 48gib-slow and 64gib. Each pod has an empty pod `securityContext`, no container `securityContext` and no initContainers. Each mounts the hostPath `/var/lib/ollama` (`DirectoryOrCreate`) at `/root/.ollama`, with `OLLAMA_MODELS=/root/.ollama/models`.
- Argo CD Application `llm` tracks `main` (path `k8s/llm`, automated prune and selfHeal). Nothing deploys from `release/v0.2.32`, and every tier rolls at once when the release PR merges.
- `get` and `describe` cannot show file ownership on a node. Every writer so far ran as UID 0, and kubelet creates a `DirectoryOrCreate` hostPath owned by root, so the directory is taken to be root-owned. The design does not rely on that, because `chown -R` re-owns whatever is there at every start.

Every DaemonSet now carries the same settings. A kustomize patch is not used, because `devops k8s deploy-stack` applies this file with `kubectl apply -f`:
- **Pod:** `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `seccompProfile: RuntimeDefault`. The owner chose UID 10001 because no host login account uses it, so neither the model directory's owner nor an escaped process maps to a person's account on a GPU node.
- **Container `ollama`:** `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`, and `/tmp` on an emptyDir (`tmp`).
- **Paths:** `HOME=/home/ollama`, with the hostPath mounted at `/home/ollama/.ollama` and `OLLAMA_MODELS=/home/ollama/.ollama/models`.
  - `ollama serve` reads or creates its key at `$HOME/.ollama/id_ed25519`. A UID that is not in the image's passwd file would otherwise get `HOME=/`.
  - `/root` cannot be reached by a non-root UID.
  - With these paths, the key and `models/` stay where they were on the host (`/var/lib/ollama`), so nothing is downloaded again. The hostPath and its type are unchanged.
- **initContainer `own-model-directory`:** runs `chown -R 10001:10001 /home/ollama/.ollama` from the same `ollama/ollama:0.34.4` image, so no second image lands on a node.
  - Security context: `runAsUser: 0`, `runAsNonRoot: false`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities: {drop: [ALL], add: [CHOWN]}`.
  - Resources: `requests.cpu: 10m` and `limits.memory: 64Mi`. The memory request defaults to the limit, so kube-linter reports nothing new for it.
  - Why it is needed: `fsGroup` does not apply to hostPath volumes; a non-root container loses an added `CAP_CHOWN` at execve, because containerd sets no ambient capabilities; and a DaemonSet cannot give each node its own PVC. Under chown(2), `CAP_CHOWN` alone lets root re-own the files, so `FOWNER` is not needed. This is the Grafana chart's `initChownData` pattern, with a read-only root filesystem added.
- **Header comment:** the manifest header and `k8s/README.md` ("GPU Placement: Ollama tiers") record the UID and the initContainer as the one exception to kube-linter's `run-as-non-root`. No ignore-check annotation is used.

**Re-scope accepted by the owner on 2026-10-09 (the issue's "Update 2026-10-09").**
- AC4 changes: some container must run as root once to give the hostPath to the ollama UID. kube-linter therefore reports `run-as-non-root` for that initContainer, one per DaemonSet, and nothing else new.
- ollama runs as UID and GID 10001, not 1000.
- The UID cannot be named once in the manifest: YAML anchors do not cross `---` documents, and `kubectl apply -f` would skip a kustomize patch. The test names it once (`OLLAMA_UID`) and asserts it for all 9 tiers.

## Acceptance Criteria
- [x] Every ollama DaemonSet's `ollama` container sets `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` and `readOnlyRootFilesystem: true`, with `seccompProfile: RuntimeDefault` at pod level and an emptyDir at `/tmp`. No other emptyDir is added: the person-run checks below look for "read-only file system" errors, and each such path gets an emptyDir.
- [x] Every ollama DaemonSet runs as UID and GID 10001 with `runAsNonRoot: true`. The model directory is given to that UID by `own-model-directory`, which holds `CAP_CHOWN` alone. `OLLAMA_MODELS` and the data mount moved off `/root`, and `HOME=/home/ollama` keeps the existing hostPath layout.
- [x] `test_every_ollama_tier_runs_unprivileged` in `tests/test_k8s_llm_gateway.py` loads every DaemonSet in `ollama-profiles.yaml`. For each one, it asserts:
  - the pod and container security contexts;
  - `HOME` and `OLLAMA_MODELS`;
  - the container's mounts;
  - the volumes, including the unchanged hostPath `/var/lib/ollama` (`DirectoryOrCreate`);
  - exactly one initContainer, `own-model-directory`, with the ollama container's image, its `chown` command, its security context and its mount.

  A new tier is covered without editing the test, and `test_ollama_profiles_define_standard_vram_tiers` still pins the 9 names. On the previous manifest the test failed with an assertion diff for every tier, not a `KeyError`. It runs no kubectl, kube-linter or network call.
- [x] kube-linter 0.8.3 over `k8s/llm/profiles/ollama-profiles.yaml` (run locally; the suite does not run it):
  - Before: 27 reports, `no-read-only-root-fs` x9, `run-as-non-root` x9 and `unset-memory-requirements` x9.
  - After: 18 reports, `run-as-non-root` x9, all `container "own-model-directory"` (the recorded exception), and `unset-memory-requirements` x9, all `container "ollama"` (out of scope: #209 removed the memory limits on purpose).
  - `no-read-only-root-fs` is 0, nothing new appears, and no ignore-check annotation is used.
- [x] `changelog.d/1060.md` records the change under `### Fixed`. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] Locally, these pass:
  - the tests that read this manifest or scan every manifest: `tests/test_k8s_llm_gateway.py`, `tests/test_k8s_gpu_matrix.py`, `tests/test_ai_gateway_portkey.py`, `tests/test_k8s.py::test_k8s_workload_resource_limits_and_probes`, `tests/test_k8s_valkey_stack.py`, `tests/test_k8s_push_secrets.py`, `tests/test_k8s_manifest_validation.py`, `tests/test_k8s_network_policies.py` and `tests/test_review_project_conventions.py`;
  - `tests/test_agent_task_files.py` and `tests/test_release_changelog_fragments.py`;
  - `ruff check` and `ruff format --check` on the test file, and `devops docs check`.

  No `src/` file changed, so mypy has nothing new to check. `uv run devops ci` runs as the pull request's CI check.
- Pending a person: the canary on one node, after this PR merges into `release/v0.2.32` and before the v0.2.32 release PR merges into `main` (Argo CD rolls every tier at once from `main`):
  1. From a checkout of `release/v0.2.32`, record each scheduled tier's models for the later comparison, and confirm that the 16gib tier has no model loaded (`ollama ps` lists none), so the canary has the GPU to itself:
     ```bash
     for t in ollama-16gib ollama-48gib ollama-48gib-slow ollama-64gib; do kubectl -n llm exec ds/$t -c ollama -- ollama list | awk '{print $1, $2}' > /tmp/$t.models; done
     kubectl -n llm exec ds/ollama-16gib -c ollama -- ollama ps
     ```
  2. Create the canary as a bare Pod named and labelled `ollama-canary`, with `restartPolicy: Never`. It must not carry the template's labels: the DaemonSet would adopt and delete a pod matching its selector, and the `ollama-16gib` Services would send gateway traffic to it. If it stays Pending for lack of CPU or memory next to the live pod, the canary cannot run on that node: delete it (`kubectl -n llm delete pod ollama-canary`) and rely on the rollout checks.
     ```bash
     uv run python -c 'import json,yaml; ds=next(d for d in yaml.safe_load_all(open("k8s/llm/profiles/ollama-profiles.yaml")) if d and d["metadata"]["name"]=="ollama-16gib"); print(json.dumps({"apiVersion":"v1","kind":"Pod","metadata":{"name":"ollama-canary","namespace":"llm","labels":{"app.kubernetes.io/name":"ollama-canary"}},"spec":{**ds["spec"]["template"]["spec"],"restartPolicy":"Never"}}))' | kubectl apply -f -
     kubectl -n llm wait --for=condition=Ready pod/ollama-canary --timeout=10m
     kubectl -n llm get pod ollama-canary -o jsonpath='{.status.initContainerStatuses[0].state.terminated.exitCode}'   # 0
     kubectl -n llm exec ollama-canary -c ollama -- id                    # uid=10001 gid=10001
     kubectl -n llm exec ollama-canary -c ollama -- sh -c 'ls -ln /dev/nvidia*'   # crw-rw-rw-, or a group the pod is in
     kubectl -n llm exec ollama-canary -c ollama -- ollama list | awk '{print $1, $2}' | diff /tmp/ollama-16gib.models -   # no output
     kubectl -n llm exec ollama-canary -c ollama -- ollama run gpt-oss:20b 'Reply with ok'
     kubectl -n llm exec ollama-canary -c ollama -- ollama ps             # PROCESSOR shows GPU
     kubectl -n llm logs ollama-canary -c ollama | grep -E 'inference compute|read-only|permission denied'   # a CUDA line, no errors
     kubectl -n llm delete pod ollama-canary
     ```
     The canary leaves that node's directory owned by 10001 while the live pod still runs as root, which keeps writing it (root holds `CAP_DAC_OVERRIDE`).
  3. If the canary fails, fix it in `release/v0.2.32` before the release PR merges, and change the test with it:
     - `/dev/nvidia*` is 0660 to a group and the log shows no CUDA line: add pod `supplementalGroups: [<that gid>]` to all 9 tiers.
     - A "read-only file system" error at a path: add an emptyDir at that path.
     - Only a demonstrated need for root: keep root with every other control set, with a manifest comment and a `k8s/README.md` note. The initContainer must stay and chown to `0:0`, because root with all capabilities dropped cannot write the 10001-owned directory the canary left.
     - Anything else, such as the NVIDIA hook failing on a read-only root: stop and return it to the owner.
- Pending a person: the rollout, after the v0.2.32 release PR merges and Argo CD syncs `llm`:
  1. Argo CD and the DaemonSets:
     ```bash
     kubectl -n argocd get application llm -o jsonpath='{.status.sync.status} {.status.health.status} {.status.sync.revision}{"\n"}'   # Synced Healthy <release merge commit>
     kubectl -n llm get ds -l llm.devops.io/provider=ollama   # READY == DESIRED; 16gib, 48gib, 48gib-slow and 64gib at 1
     ```
  2. Each scheduled tier's pod is Ready, runs as 10001, sees its GPU and still has its models. Expected per tier: `0 0` (init exit code, restarts), `uid=10001 gid=10001`, a GPU name, no `diff` output, and a CUDA `inference compute` line with no "read-only" or "permission denied":
     ```bash
     for t in ollama-16gib ollama-48gib ollama-48gib-slow ollama-64gib; do
       kubectl -n llm get pods -l app.kubernetes.io/name=$t -o jsonpath='{.items[0].status.initContainerStatuses[0].state.terminated.exitCode} {.items[0].status.containerStatuses[0].restartCount}{"\n"}'
       kubectl -n llm exec ds/$t -c ollama -- id
       kubectl -n llm exec ds/$t -c ollama -- nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
       kubectl -n llm exec ds/$t -c ollama -- ollama list | awk '{print $1, $2}' | diff /tmp/$t.models -
       kubectl -n llm logs ds/$t -c ollama | grep -E 'inference compute|read-only|permission denied'
     done
     ```
  3. A restart re-owns a directory that 10001 already owns: `kubectl -n llm rollout restart ds/ollama-16gib && kubectl -n llm rollout status ds/ollama-16gib --timeout=10m` completes, and the first command of step 2 then prints `0 0` for `ollama-16gib`.
  4. Each tier loads and answers a model through the gateway. Use models that each route to one tier only (`k8s/llm/gateway/configmap.yaml`): `gpt-oss:20b` (16gib), `devops-coder` (48gib), `deepseek-r1:70b` (64gib), and `devops-background` and `bge-m3:latest` (48gib-slow). Each call returns a `choices` entry (the embedding, a vector length), and `kubectl -n llm exec ds/<tier> -c ollama -- ollama ps` then shows the model on 100% GPU:
     ```bash
     kubectl -n llm port-forward svc/llm-gateway 4000:4000 &
     KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
     for m in gpt-oss:20b devops-coder deepseek-r1:70b devops-background; do
       curl -s localhost:4000/v1/chat/completions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
         -d "{\"model\":\"$m\",\"max_tokens\":64,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with ok\"}]}" | jq '.choices[0].message // .error'
     done
     curl -s localhost:4000/v1/embeddings -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
       -d '{"model":"bge-m3:latest","input":"ok"}' | jq '.data[0].embedding | length'
     ```
  5. Record the result per tier in this item's pull request.

## Deliverables
- [x] `k8s/llm/profiles/ollama-profiles.yaml`: the pod and container security contexts, `HOME`, the moved mount and `OLLAMA_MODELS`, the `/tmp` emptyDir and the `own-model-directory` initContainer in all 9 DaemonSets, and the header comment that records the exception.
- [x] `tests/test_k8s_llm_gateway.py`: `OLLAMA_UID`, `_ollama_privileges` and `test_every_ollama_tier_runs_unprivileged`.
- [x] `k8s/README.md`, "GPU Placement: Ollama tiers": a paragraph on the UID, the controls, the initContainer and the kube-linter exception.
- [x] `changelog.d/1060.md`.
- Out of scope, as the issue records: memory limits for the `ollama` container (kube-linter `unset-memory-requirements` x9), which #209 removed on purpose.
- Not in this item, as the issue's key question decides: raising the `llm` namespace's Pod Security `enforce` level. The tiers keep it at `privileged` regardless, because Pod Security's baseline level forbids hostPath volumes.

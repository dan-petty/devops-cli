# Tasks

## 1. The tunnel replicas prefer different nodes and keep one up through a drain

- [x] Add failing tests: the pod template of Deployment `cloudflared` has one preferred `podAntiAffinity` term on `kubernetes.io/hostname` that selects its own pods and no required term; the kustomization applies a `policy/v1` PodDisruptionBudget with `minAvailable: 1` and `unhealthyPodEvictionPolicy: AlwaysAllow` that selects the same pods
  - Verification: `uv run devops ci test tests/test_k8s_cloudflared.py`
- [x] Add the preferred anti-affinity term to `k8s/cloudflared/deployment.yaml`, add `k8s/cloudflared/pdb.yaml`, and list it in `k8s/cloudflared/kustomization.yaml`
  - Verification: `uv run devops ci test tests/test_k8s_cloudflared.py` and `kube-linter lint k8s/cloudflared/`
- [x] Describe the placement and `pdb.yaml` in `k8s/README.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1023-cloudflared-spread`
- Pending a person: after Argo CD syncs the merge, `kubectl -n cloudflared get pods,pdb -o wide` shows the two pods on different nodes and the PodDisruptionBudget with 1 allowed disruption, and `kubectl drain <node> --dry-run=server` of one pod's node evicts that pod while the other stays running.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

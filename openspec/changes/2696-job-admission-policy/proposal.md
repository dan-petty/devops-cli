# Proposal

## Why

Issue #2696. The Role `roadmap-service-jobs` lets the Service create Jobs in namespace `devops` (#2667). Kubernetes RBAC cannot limit `create` to a name. So the Role can create any Job. Pod Security `restricted` does not stop a bad Job at creation: the `enforce` mode checks pods, and it only warns and audits for a workload such as a Job. The Job is stored, and only its pod is refused later. A Job of the Service can name any image, any ServiceAccount of the namespace and any volume that `restricted` admits, such as a Secret volume. It can also read a Secret through `envFrom` or `env.valueFrom`.

Today this gives the Service no new secret: the Service pod holds Secret `devops-cli` already, and that Secret is the only one in the namespace. That stops being true when a second Secret appears there. Then a compromise of the Service reaches that Secret through a Job. A policy that pins the Jobs of the Service closes the gap before it opens.

## What Changes

- A ValidatingAdmissionPolicy and a binding in `k8s/devops/roadmap-service/`. The binding covers `CREATE` and `UPDATE` of `jobs` in namespace `devops`. The policy applies only to the user `system:serviceaccount:devops:roadmap-service`. It refuses a Job unless:
  - the Job has one container, no init container, and an image that is `ghcr.io/dan-petty/devops-cli/runner` alone or followed by `:` or `@` (the tag or digest form of the CronJob after Image Updater);
  - the pod uses ServiceAccount `devops-cli` and sets `automountServiceAccountToken: false`;
  - every `envFrom` entry names Secret `devops-cli`, and no `env` entry uses `valueFrom`;
  - the volumes are only `tmp` and `home` (`emptyDir`) and `config` (ConfigMap `devops-cli-config`);
  - the pod sets no `hostNetwork`, `hostPID` or `hostIPC`;
  - the Job sets `backoffLimit: 0` and an `activeDeadlineSeconds` of 7200 at most.
- `failurePolicy: Fail` and the validation action `Deny` with `Audit`. Other identities (the CLI user, Argo CD, the CronJob controller) do not match, so the policy never evaluates their Jobs.
- A test in `tests/test_k8s_job_admission_policy.py` renders `k8s/devops`, evaluates the CEL of the policy with an open CEL library against the Job that `build_job` makes from CronJob `devops-cli-runner`, and against Jobs that break each rule. A change to the template that the policy refuses fails in CI.
- The dev dependency `cel-expr-python`.
- `k8s/README.md` describes the policy and what it does and does not guarantee. The line that says the policy is planned changes to describe it.
- A consumer observes a manifest, so the change carries a spec delta: one added requirement in the capability `roadmap-implement-runner`.
- The change needs no change in Argo CD. AppProject `homelab` already allows every cluster-scoped kind, and Application `devops` syncs `k8s/devops` through the overlay with prune and self-heal. Rollout is Argo CD after the merge.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: one added requirement, the admission policy that pins the Jobs of the Service.

## Impact

- `k8s/devops/roadmap-service/admissionpolicy.yaml` (new), `k8s/devops/roadmap-service/kustomization.yaml`, `k8s/README.md`.
- `tests/test_k8s_job_admission_policy.py` (new), `pyproject.toml` and `uv.lock` (dev dependency).

## Feasibility

The premise is that the cluster can enforce a ValidatingAdmissionPolicy, and that the CEL of the policy can be tested offline. Both were checked against the real system with read-only commands.

- `kubectl version` gives server `v1.31.4+k3s1`. ValidatingAdmissionPolicy is GA (`admissionregistration.k8s.io/v1`) from Kubernetes 1.30.
- `kubectl api-resources` lists `validatingadmissionpolicies` and `validatingadmissionpolicybindings` in `admissionregistration.k8s.io/v1`.
- The metric `apiserver_admission_controller_admission_duration_seconds_count{name="ValidatingAdmissionPolicy"}` on `/metrics` is far above zero for `CREATE` and `UPDATE`, so the admission plugin runs.
- `kubectl get validatingadmissionpolicies,validatingadmissionpolicybindings` shows none. The new objects collide with nothing.
- Namespace `devops` holds Secret `devops-cli` and ConfigMap `devops-cli-config` (and `kube-root-ca.crt`), and enforces `restricted`. ServiceAccounts `devops-cli`, `roadmap-service` and `default` exist. The label `kubernetes.io/metadata.name=devops` that the binding selects is set by Kubernetes.
- `k8s/argocd/apps/projects.yaml`: AppProject `homelab` has `clusterResourceWhitelist` of group `*` and kind `*`, so it admits the two cluster-scoped kinds. `k8s/argocd/apps/devops.yaml`: Application `devops` syncs `k8s/overlays/homelab/devops`, which is `k8s/devops`, with `prune` and `selfHeal`. Nothing in Argo CD changes.
- The template, as `kubectl kustomize k8s/devops` renders it, gives the values to pin: image `ghcr.io/dan-petty/devops-cli/runner`, `backoffLimit: 0`, `activeDeadlineSeconds: 7200`, volumes `tmp`, `home` and `config`. Image Updater writes `runner:latest@sha256:<digest>` into the Application, so the policy accepts the repository with `:` or `@`.
- The CEL test tool. The policy uses only the standard CEL language (operators, `has`, `all`, `size`, `startsWith`). The standard CEL runtime in Python then gives the same answer as the CEL of the API server, which Kubernetes builds on `cel-go`. Three libraries were installed and run on the real expressions in a scratch environment on Python 3.14.10: `cel-expr-python` 0.1.3, `cel-python` 0.5.0 and `common-expression-language` 0.10.0. All three gave the same answers on a sample of expressions that use `has`, `all`, `startsWith`, `size`, `in` and a missing key. `cel-expr-python` was chosen. See the design.

## Existing Tool Considered

ValidatingAdmissionPolicy is built in and adds no component. Kyverno and OPA Gatekeeper cover the same need, but each adds a controller and webhook to the cluster, so they are not chosen. For the offline test, `cel-expr-python` (Apache-2.0, published by the CEL project as a Python wrapper of its C++ implementation) evaluates the CEL. The change builds no CEL interpreter and deletes no internal code.

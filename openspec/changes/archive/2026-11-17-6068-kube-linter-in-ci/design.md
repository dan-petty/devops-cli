# Design

## Decisions
- The lint input is the build of each path source of each Application, one file for each source (`<application>-<index>.yaml`) in one folder, and one kube-linter run reads the folder. A check that reads two objects, such as `non-isolated-pod`, then finds the NetworkPolicy of another Application. Measured: `non-isolated-pod` gave 28 findings on the chart builds alone and 3 when they were linted together with the path sources.
- `write_path_renders` puts the fetched repositories beside the folder of the builds, so kube-linter reads only the builds. It builds up to 8 sources at a time: the build of the 15 sources took 10.7 s one at a time and 5.3 s with 8 workers, on a loaded host.
- The command passes `--config <repository>/.kube-linter.yaml`, because kube-linter reads a `.kube-linter.yaml` only from its working directory, which is the folder of the builds.
- A row of its own, `kube-linter`, runs the lint, not the `k8s` row: each row of `tests/gate` runs only the main of its module, and a row of its own can be skipped by name.
- The Static Analysis job installs kube-linter with `devops install-tools --tool kube-linter`, as it installs Trivy, OpenTofu and OpenSpec: the pin and its sha256 are in `tools.lock`.
- An exception is the annotation `ignore-check.kube-linter.io/<check>` on the object, with the reason and the issue that removes it as its value. For the Ollama tiers, a patch of `k8s/llm/profiles/kustomization.yaml` adds the `run-as-non-root` exception, because `devops ai gateway render` writes two tiers and drops their annotations.
- Six Deployments with no strategy and the GPU feature discovery DaemonSet set `RollingUpdate` explicitly. For 3 replicas or fewer, `maxUnavailable: 0` and `maxSurge: 1` are the values that Kubernetes already used, so the rollout does not change.
- The prune protection check is a `required-annotation` check of PersistentVolumeClaims: the deleted tests checked the claims `renovate-cache` and `roadmap-service-home`.

## Rejected alternatives
- Lint the Helm chart sources too: rejected for this change. The 19 chart builds give 113 findings, and the values of 5 charts cannot annotate their workloads, so a finding there has no narrow exception (#6106).
- Run kube-linter in the Security Scan step on the tree: kube-linter reads only the root kustomization of `k8s/`, and a run on `.` took more than 120 s on the devcontainer.
- A CEL check (`cel-expression`) that each Namespace keeps `Prune=false,Delete=false`: kube-linter has no object kind for a Namespace, so the check reads each object and compiles the expression for each one. It took the run from 1.0 s to 28.9 s on a loaded host. Namespaces keep their tests in `tests/config/test_k8s_devops_runtime.py` and `tests/invariants/test_k8s_argocd_apps.py`.
- A digest check (the `latest-tag` template with an allow list of `@sha256:`): 7 third-party images of the path sources name no digest today. #6067 pins them first.
- Exclude `no-liveness-probe` and `no-readiness-probe` for the CronJobs in the config: kube-linter scopes a check only by object kind, and `DeploymentLike` holds the CronJobs. Each CronJob has the annotations.
- A digest-pinned kube-linter image as a step of its own, as `actionlint` runs: the lint needs the build of the sources first, which `devops k8s lint` makes.

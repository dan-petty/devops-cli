# Proposal: #3700

## Why
The runner Job runs `prepare`, `agent` and `publish` in one container, so the agent and the App key share one process tree and one home (#2695). Closes #3700.

## What Changes
- CronJob `devops-cli-runner` runs the init containers `prepare` and `agent` and the container `publish`, of one image. `build_job` gives each its `--phase` and `--work /run/roadmap` (#6690).
- Volumes: `run` at `/run/roadmap` (read-write in `prepare` and `agent`, read-only in `publish`), `state` at `/run/roadmap/state` (read-write in `prepare`, read-only in `publish`, no mount in `agent`), and an own tmp and home in each container. `config` is read-only.
- Keys: the App key only in `prepare` and `publish`, the model key only in `agent`. No new Secret key and no new setting.
- Sizes: `agent` keeps the row of `RUNNER_SIZES`; `prepare` and `publish` have one small fixed row.
- Policy `roadmap-service-jobs`: one variable for the containers and the init containers, used by each rule of a container; the exact names; the key of each container; the mounts of each container; no `shareProcessNamespace`, `restartPolicy` or `restartPolicyRules`; the one-container shape only on an UPDATE; sync wave `-1` for the policy and its binding.
- The renovate `token` init container names the cluster and the namespace, which the telemetry check now finds in init containers too.
- `docs/CLUSTER.md` (Template, Admission policy, Guarantees, Size, Fix-checks Jobs), SECURITY.md and docs/roadmap/implement.md state the layout.

## Capabilities
- `roadmap-implement-runner`: the template, the keys and homes, and the policy rules of the three containers.

## Impact
- The change fits one pull request.
- `k8s/devops/cronjob-runner.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`, `k8s/devops/renovate/cronjob.yaml`.
- The gate checks of `tests/gate/k8s_checks/`, and two test modules that now build their CronJob.
- The interim git controls and the symlink stop stay; #6691 deletes them after this item is live.

## Feasibility
The Service runs 0.191.1, which holds the readers of #6690 (0.190.0). The CronJob of the cluster runs the runner image that the 0.191.1 release verified (digest `sha256:c64faac5…`), which takes `--phase` and `--work` for implement and fix-checks. No Service row starts a fix-conflict Job. The agent phases write only in `--work`, their home and `/tmp`. With #6743, `publish` writes nothing in the run folder, so this change merges only after a release holds #6743 and CronJob `devops-cli-runner` runs the runner image of that release.

## Existing Tool Considered
Kubernetes init containers give the order and a Secret key for each container, and a ValidatingAdmissionPolicy with CEL pins the layout. This change builds nothing else.

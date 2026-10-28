# Design

## The stop switch pauses Argo CD with `automated.enabled: false`

The stop switch turns off automated sync for `bootstrap`, `cluster` and `devops`, in this order, with a merge patch that sets `spec.syncPolicy.automated.enabled` to `false`. Each of the three self-heals, and `bootstrap` manages `cluster`, which manages `devops`. A scale by hand stays only when all three are paused.

Rejected: **a patch that sets `spec.syncPolicy.automated` to `null`.** It also removes `prune` and `selfHeal` from the live object. The repository pauses with `enabled: false` (`_pause_args` in `src/devops_cli/k8s/volume_move.py`, and `k8s/README.md`, Pausing an Application), and `tests/test_k8s_argocd_apps.py` pins `enabled: true` in git, so the stop switch uses the same field.

## The go-live check uses a ping as the test delivery

A ping goes to the hook that a person configured, with that hook's secret, and the Service answers it with HTTP 200 and counts it, but starts no round. So the check proves the route, the tunnel and the secret, and adds no GitHub request to the first hour.

Rejected: **a redelivery of an `issues` delivery.** It starts a round for the repository in the first hour, when each due lane runs already.

## The comment in the manifest names no command

The stop switch has seven steps, and some of them only a person can do. The comment in `deployment.yaml` names the identity the Service acts as and points to `k8s/README.md`, so the steps live in one document.

## The go-live check runs deploy-stack and restarts the pod

Argo CD syncs `k8s/devops/`, which holds no ConfigMap. Only deploy-stack renders `devops-cli-config`, because the render takes `service.repos` and the App's settings from the active config, which git does not hold. On a cluster that Argo CD manages, deploy-stack applies the ConfigMap and does not restart the pod. So the go-live check runs deploy-stack from `main`, reads `max_retries` from the live ConfigMap, and restarts the pod.

Rejected: **`DEVOPS_CLI_AI_MAX_RETRIES=1` in the environment of the deployment and of the CronJob.** Argo CD would apply it with the replica count, but the retry count would then have two sources, the template and the manifests, and issue #2494 puts it in the template.

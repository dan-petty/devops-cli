# Proposal: #5306

## Why
Open WebUI allows every CORS origin. Its start log has the line `WARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.` `k8s/llm/values-open-webui.yaml` sets no `CORS_ALLOW_ORIGIN`, so Open WebUI uses its default `*`. Its API allows credentials, so a page on a different origin can read the replies to requests that carry the session of a signed-in user. Its Socket.IO server accepts a connection from any origin. The real host of Open WebUI must stay out of git (AGENTS.md rule 10). Closes #5306.

## What Changes
- A new ConfigMap `llm/open-webui-origins` (`k8s/ingress/open-webui-origins.yaml`) holds `CORS_ALLOW_ORIGIN`: the HTTPS origin of each host of Ingress `llm/open-webui-ingress`, in the same order, under the placeholder domain (`https://chat.example.com;https://homelab.example.com`). `k8s/ingress/kustomization.yaml` lists it, so the Argo CD Application `ingress` renders it beside the Ingress.
- `k8s/llm/values-open-webui.yaml` adds a `configMapRef` to that ConfigMap in `extraEnvFrom`. The reference is not optional: the pod does not start without the ConfigMap, so Open WebUI never starts with its default.
- `_host_fields` (`src/devops_cli/k8s/argocd_overrides.py`) also returns each `data` value of a ConfigMap that holds the placeholder. `host_patches` tests and then replaces each such value. Thus `devops k8s deploy-stack` writes the configured domain into the origins as a Kustomize patch on Application `ingress`, in the same run as the hosts. The Argo CD gate allows the placeholder in such a value, and still refuses it in each other field of a ConfigMap.
- Without Argo CD, `deploy-stack --stack llm` applies the file under the configured domain before it installs the charts (`MANIFESTS_BY_STACK["llm"]`).
- A check of the `k8s` row of `devops ci` keeps the origins equal to the Ingress hosts, before and after the patches.
- `k8s/README.md` lists the new value in "Homelab Values at Deploy Time", and tells when Open WebUI reads the origins and how they change.
- A manifest and the behavior of `deploy-stack` change, so the change has a spec delta.

## Capabilities
- Modified: `gitops-host-overrides`. It adds the requirements "deploy-stack sets the configured domain in ConfigMap data values" and "Open WebUI allows only the origins of its Ingress hosts".

## Impact
- At the merge, the Application `ingress` creates ConfigMap `llm/open-webui-origins`, and the Application `open-webui` restarts the pod of StatefulSet `open-webui` one time, because its pod template gets a new `envFrom` entry. No other workload restarts.
- Until deploy-stack covers the new ConfigMap, the ConfigMap holds the placeholder origins. Stage the domain before the merge with `devops k8s deploy-stack --stack infra --argocd-revision <head of the pull request>`. Kustomize skips the patch of the ConfigMap until the ConfigMap exists.
- A browser that opens Open WebUI at an origin that is not an Ingress host, such as a NodePort URL on minikube or a port-forward to localhost, gets no Socket.IO connection. A page on the same origin and a request with no `Origin` header, such as a request of the CLI, are not changed.
- deploy-stack writes the same patches as before for each object that `main` renders (Feasibility). No new dependency, setting or command.
- The change fits one pull request.

## Feasibility
- Upstream source of Open WebUI v0.11.4, the pinned image, and of v0.13.3, the version of #5086: `backend/open_webui/config.py` reads `CORS_ALLOW_ORIGIN = os.getenv('CORS_ALLOW_ORIGIN', '*').split(';')`, logs the warning when the list is `['*']`, and refuses an origin without an `http` or `https` scheme or without a host. `backend/open_webui/main.py` gives the list to `CORSMiddleware` with `allow_credentials=True`. `backend/open_webui/socket/main.py` gives the same list to the Socket.IO server as `cors_allowed_origins`. python-engineio (`base_server.py`, `_cors_allowed_origins`, and the `Origin` check of `async_server.py`) refuses a connection whose `Origin` is not in such a list.
- Chart `open-webui` 18.3.0 (`helm pull`): no value sets CORS, and the chart renders `extraEnvFrom` as the `envFrom` of the container.
- Live cluster, read only, on 2026-11-13: StatefulSet `llm/open-webui` has no `CORS_ALLOW_ORIGIN`. The Application `ingress` holds the host patches of 19 objects in `spec.source.kustomize`.
- The fix that the issue proposes, a Helm value override on the Application `open-webui`, does not stay in place. That Application has `spec.sources` (the chart and `$values`), and `application_source` refuses `spec.sources`. In Argo CD v3.6.1 (`controller/sync.go`, `normalizeTargetResources` and `restoreNonIgnoredFields`), `RespectIgnoreDifferences` keeps an ignored live field only inside maps. For the list `spec.sources`, it applies the list from git. The CRD gives `spec.sources` no list type, so server-side apply also replaces the list as one value. Each sync of `cluster` would thus remove the override. This change uses the Kustomize patches of a single-source Application, as the other hosts do.
- Kustomize: `kubectl kustomize` of a scratch overlay applied a JSON patch with the target `{group: "", version: v1, kind: ConfigMap}` to `/data/<key>`, and skipped a patch whose target matched no object.
- Same patches on `main`: a scratch script ran `host_patches` of `origin/main` and of this branch on the renders of `devops`, `ingress` and `mattermost` at `origin/main`. The two results were equal for each Application. On this branch, `ingress` renders 20 objects to patch (19 on `main`), and the new one is the ConfigMap.

## Existing Tool Considered
Open WebUI reads its allowed origins only from `CORS_ALLOW_ORIGIN`, and its chart has no value for them. Argo CD has no deploy-time variable for a value in git. Kustomize `replacements` copies one field, or one segment of a field, from a source object, and that source would hold the real domain in git. The change thus extends the patch builder of deploy-stack by one kind. Cost: about 200,000 tokens and 3 hours to build, about 5,000 tokens a month to keep, and about 30,000 tokens to fix. The change deletes no internal code.

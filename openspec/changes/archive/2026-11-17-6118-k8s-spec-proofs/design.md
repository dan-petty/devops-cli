# Design

## Decisions

### A check of the `k8s` gate row is a validator
`uv run devops ci --check --only k8s` runs the `check_*` functions of `tests/gate/k8s_checks` on the render of `kubectl kustomize`. #6080 names this command as a proof, and the guard of #6075 counts only pytest modules. So a scenario names the row when one of its checks holds the rule, for example each rule of the gateway database.

### A NetworkPolicy is proved by a throwaway pod
A connect from a throwaway pod (`kubectl run --rm -i --restart=Never`, then `nc -w 3 <host> <port>`) shows what the policy allows, the method of `src/devops_cli/k8s/service_probe.py`. Where `devops k8s searxng-check` or `devops k8s crawl4ai-check` already runs such a probe, the scenario names the check.

### A control of Pod Security is proved by the API server and Kube-linter
Namespaces `devops` and `gitea` enforce the `restricted` level, so `kubectl rollout status` completes only for an admitted pod. `kubectl get -o jsonpath` reads the user and the read-only root of the admitted pod with no exec into a workload, and `devops k8s lint` reports the controls that the `restricted` level does not hold.

### An alert rule is proved by Prometheus
`devops prometheus rules` shows that Prometheus loaded a rule with the health `ok`, and `devops prometheus query 'ALERTS{...}'` shows its state.

### A requirement that only restates a file goes
A requirement goes when its only content is a value that a person can read in the file: a document that repeats a table or a list of another file, a comment, the text of an alert, the example ConfigMap. Its Migration names the requirement that keeps the rule, or says that the file keeps the text.

### A scenario name that says "A test reads" needs a new requirement name
OpenSpec 1.17.0 refuses a MODIFIED block that omits a scenario name of the current spec, and refuses a requirement that is both REMOVED and ADDED in one delta. So a requirement whose scenario name says "A test reads" goes out as REMOVED and comes back as ADDED under a new name with the same rule. The other requirements keep their scenario names in a MODIFIED block with new steps.

### A scenario of a table of the source code stays
The cluster secret table, `OPTIONAL_FEATURE_SECRETS` and the deploy-stack tables are source code, and `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_grafana_renderer_optional.py` and `tests/commands/k8s/test_k8s_gitea.py` test them. Such a scenario stays, as #6083 allows.

### The first area
The area holds the capabilities of Kubernetes, the cluster and its stacks: `k8s-*`, `cluster-*`, `gitops-*`, the `*-service` stacks and the stack capabilities of Gitea, the gateway database, Qdrant, Crawl4AI, the image renderer, cloudflared and the placement of claims. The release pins (`loki-release-pin`, `traefik-release-pin`, `ollama-release-pin`, `ollama-image-pin`, `cloudflared-release-pin`) go with the images area, and `monitoring-collectors`, `log-and-metric-retention` and `grafana-plugins` go with the monitoring and Renovate areas. Open pull requests change `ai-gateway-routing`, `roadmap-service-deployment` and `project-metrics-dashboard`, so those capabilities wait.

## Rejected alternatives
- Keep a scenario name that says "A test reads" with new steps: the census keeps the hit, and the name tells the stage job to plan a test.
- Read the value of each control from the live object with `kubectl get -o jsonpath`: this moves the value test to the cluster. A scenario uses such a read only where no probe of the behavior exists.
- One pull request for every capability: about 330 scenarios in 95 capabilities is too large to review, and #6083 asks for one area per pull request.

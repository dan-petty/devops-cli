# Design

## Decisions

- **Select the label that `build_job` sets.** The pod label of every Job is `devops-cli-job`. The admission policy, the telemetry variable and the Job queries (`-l app.kubernetes.io/name=devops-cli-job`) use the same value. The policies follow it.
- **No second label.** The issue asked if a runner Job of the Service needs a second label for the policy. It does not: a new label needs a change of `build_job`, of the admission policy and of the template, and it protects nothing more. The owner decided that `devops-cli-job` pods may use the server.
- **Drop `devops-cli-runner` from the policies.** No pod carries it: the CronJob never runs on its schedule. A rule for a pod that cannot exist is dead and widens the policy for the day somebody makes such a pod by hand.
- **The perimeter stays closed.** The perimeter policy is not changed. Each of the two policies adds one rule: TCP 8001 to the server pods, and TCP 8001 from the clients. No namespace selector and no address block is used.
- **One test over both policies.** The test builds a Job with `build_job` from the committed CronJob and compares its pod label with the clients that the two policies admit. A label change in one place fails the test.

## Rejected alternatives

- **A second label for the runner Jobs.** Rejected, as above.
- **Route the Jobs through the LiteLLM gateway.** Not rejected: it is a separate decision. It needs an egress rule for the gateway, an ingress rule for the server and a gateway MCP configuration. This change keeps the direct path.
- **An ipBlock for the ClusterIP of the Service.** Rejected: a pod selector is stable, and a cluster IP is not.

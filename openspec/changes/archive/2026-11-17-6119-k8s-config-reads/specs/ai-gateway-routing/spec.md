## MODIFIED Requirements

### Requirement: A gateway attempt ends before the deadline of the call
The router `timeout` of `k8s/llm/gateway/config.yaml` and the `timeout` of each deployment SHALL be less than the defaults of `ai.request_timeout_seconds` and `roadmap.implement.request_timeout_seconds`, so the gateway ends a stuck attempt and can retry it or fall back before the client ends the call. The default of `ai.request_timeout_seconds` SHALL be less than `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS` and the `activeDeadlineSeconds` of `k8s/devops/cronjob-runner.yaml`.

#### Scenario: The timeouts nest
- **WHEN** a person runs `kubectl -n llm get configmap -l app.kubernetes.io/name=llm-gateway -o yaml` and `kubectl -n devops get cronjob devops-cli-runner -o yaml` on the cluster
- **THEN** the router timeout and each deployment timeout of the gateway config are less than each default call deadline, and the default of `ai.request_timeout_seconds` is less than the stage margin and the `activeDeadlineSeconds` of the runner CronJob

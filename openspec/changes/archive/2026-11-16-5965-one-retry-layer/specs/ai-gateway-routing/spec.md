## ADDED Requirements

### Requirement: A gateway attempt ends before the deadline of the call
The router `timeout` of `k8s/llm/gateway/config.yaml` and the `timeout` of each deployment SHALL be less than the defaults of `ai.request_timeout_seconds` and `roadmap.implement.request_timeout_seconds`, so the gateway ends a stuck attempt and can retry it or fall back before the client ends the call. The default of `ai.request_timeout_seconds` SHALL be less than `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS` and the `activeDeadlineSeconds` of `k8s/devops/cronjob-runner.yaml`.

#### Scenario: The timeouts nest
- **WHEN** a test reads the gateway config, the settings defaults and the runner CronJob
- **THEN** the router timeout and each deployment timeout are less than each default call deadline, and the default of `ai.request_timeout_seconds` is less than the stage margin and the runner Job deadline

### Requirement: A direct gateway call is sent again only after a failed connect
`LLMClient` with provider `gateway` SHALL send a call again only when its connect failed or it got no connection from the pool, at most `ai.max_retries` + 1 times. It SHALL not send a call again after a status of the gateway. A client of another provider SHALL keep the retries of its transport.

#### Scenario: The gateway answers 503
- **WHEN** `ai.max_retries` is 3 and the gateway answers a call with status 503
- **THEN** the gateway got 1 call, and the client raises `AIClientError` with status 503

#### Scenario: Each connect fails
- **WHEN** `ai.max_retries` is 3 and each connect to the gateway fails
- **THEN** the transport saw 4 calls, and the client raises `AIClientError`

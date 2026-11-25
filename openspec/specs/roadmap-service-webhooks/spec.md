# roadmap-service-webhooks Specification

## Purpose
Defines how the public webhook route of the roadmap Service guards itself: the Traefik rate limit in front of the route, and the deliveries that the route refuses before it reads their body.

## Requirements

### Requirement: The route refuses an unsigned delivery before it reads the body
The webhook route SHALL refuse a delivery with no `X-Hub-Signature-256` header, or an empty one, with HTTP 401 and the error `missing signature`, before it reads the body. It SHALL count the delivery once under the outcome `rejected`.

#### Scenario: An unsigned delivery
- **WHEN** a delivery of the `issues` event comes with no signature header
- **THEN** the route answers 401 with `{"error": "missing signature"}`
- **AND** the route does not read the body
- **AND** the deliveries counter has one `rejected` delivery of the `issues` event

#### Scenario: A delivery with an empty signature header
- **WHEN** a delivery of the `issues` event comes with an empty signature header
- **THEN** the route answers 401 with `{"error": "missing signature"}`, and does not read the body

### Requirement: The route refuses a delivery that declares a length above the cap before it reads the body
The webhook route SHALL refuse a delivery whose `Content-Length` is above `CONST_SERVICE_MAX_BODY_BYTES` with HTTP 413 and the error `payload too large`, before it reads the body. It SHALL count the delivery once under the outcome `rejected`.

#### Scenario: A delivery that declares a length above the cap
- **WHEN** a signed delivery of the `issues` event declares a `Content-Length` one byte above the cap
- **THEN** the route answers 413 with `{"error": "payload too large"}`
- **AND** the route does not read the body
- **AND** the deliveries counter has one `rejected` delivery of the `issues` event

### Requirement: The route reads the body of a signed delivery within the cap
The webhook route SHALL read the body of a delivery with a signature header and no declared length above the cap, and SHALL check its signature.

#### Scenario: A signed delivery within the cap
- **WHEN** a delivery of the `issues` event comes with a signature that no secret made
- **THEN** the route reads the body and answers 401 with `{"error": "invalid signature"}`

### Requirement: Traefik limits the deliveries of the webhook route
The Traefik Middleware `devops/roadmap-service-rate-limit` SHALL let 60 requests a minute through, with a burst of 60, in one bucket for each value of `Cf-Connecting-Ip`. Each Ingress `devops/roadmap-service` that Argo CD or deploy-stack applies SHALL name it as `devops-roadmap-service-rate-limit@kubernetescrd`. Only `k8s/devops/roadmap-service/ingress.yaml` SHALL hold the Ingress.

#### Scenario: Argo CD renders the devops Application
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders the objects of Application `devops`
- **THEN** the render holds the Middleware `devops/roadmap-service-rate-limit` with `average: 60`, `period: 1m`, `burst: 60` and `sourceCriterion.requestHeaderName: Cf-Connecting-Ip`
- **AND** the Ingress `devops/roadmap-service` of the render names `devops-roadmap-service-rate-limit@kubernetescrd`

#### Scenario: deploy-stack applies the Ingress
- **WHEN** a test reads the Ingress `devops/roadmap-service` in `k8s/devops/roadmap-service/ingress.yaml`
- **THEN** it names `devops-roadmap-service-rate-limit@kubernetescrd`
- **AND** the native `devops` stack applies `middleware.yaml` before `ingress.yaml`

#### Scenario: The environment routes hold no copy
- **WHEN** a test reads the Ingresses of `k8s/ingress/ingress-routes.yaml`
- **THEN** none of them is in namespace `devops`

### Requirement: The runbook counts each answer of the route, the 429 of the rate limit included
The subsection Webhook route of `docs/CLUSTER.md` SHALL count the answers of the route with `traefik_router_requests_total`, which Traefik counts before the middlewares of the router, so that the count includes each HTTP 429 of the rate limit.

#### Scenario: An operator counts the answers of the route
- **WHEN** an operator reads the query of the subsection Webhook route in `docs/CLUSTER.md`
- **THEN** the query is `sum by (code) (increase(traefik_router_requests_total{service="devops-roadmap-service-8000@kubernetes"}[15m]))`
- **AND** the service in the query is the backend of the Ingress `devops/roadmap-service`, as `<namespace>-<name>-<port>@kubernetes`

### Requirement: Only the tunnel reaches Traefik from outside the cluster
The Traefik values SHALL keep the Service of Traefik `ClusterIP`, and the `web` entrypoint SHALL open no host port and no node port, so that each request from outside the cluster comes through Cloudflare, which writes `Cf-Connecting-Ip`.

#### Scenario: A test reads the Traefik values
- **WHEN** a test reads `k8s/ingress/traefik-values.yaml`
- **THEN** `service.spec.type` is `ClusterIP`, and `ports.web` has no `hostPort` and no `nodePort`

### Requirement: The consumer events are a subset of the hook events
Each event that a GitHub consumer of the Service takes, and each webhook event that a batch key of a due-table row names, SHALL be an event of `CONST_ROADMAP_WEBHOOK_EVENTS`, the events that `devops repos onboard` requires of the repository hook (row 12).

#### Scenario: A test reads the consumers of the Service
- **WHEN** a test reads the events of each GitHub consumer of `service_consumers` and the webhook batch keys of `DEFAULT_DUE_TABLE`
- **THEN** each consumer event is in `CONST_ROADMAP_WEBHOOK_EVENTS`, and each batch key event is a consumer event

### Requirement: The consumer takes the pull request, review, check and release events
The event set of the roadmap consumer, `CONST_ROADMAP_WEBHOOK_EVENTS`, SHALL hold `issues`, `pull_request`, `pull_request_review`, `check_suite`, `issue_comment` and `release`, and step 8 of the roadmap-service runbook, `docs/CLUSTER.md`, SHALL name the same events. `CONST_ROADMAP_INTAKE_BATCH_KEYS` SHALL hold no comment key and no release key, so a comment and a release run no intake batch.

#### Scenario: The event set holds the pull, review and check events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review`, `check_suite` and `issue_comment`

#### Scenario: The runbook step and the event set name the same events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS` and step 8 of `docs/CLUSTER.md`
- **THEN** each event of the set is named in that step

#### Scenario: The event set holds the pull, review, check and release events
- **WHEN** a test reads `CONST_ROADMAP_WEBHOOK_EVENTS`
- **THEN** the set holds `issues`, `pull_request`, `pull_request_review`, `check_suite`, `issue_comment` and `release`

### Requirement: The payload holds the comment and the pull request marker
`GitHubWebhookPayload` SHALL parse an optional `comment` that holds `body`, `author_association` and `created_at`, and `WebhookIssue` SHALL parse an optional `pull_request` marker. A payload that holds neither SHALL validate as it did before.

#### Scenario: An issue comment payload
- **WHEN** a test validates an `issue_comment` payload that holds a comment and an `issue.pull_request` marker
- **THEN** the payload holds the comment body, its author association and its time, and the issue holds the pull request marker

#### Scenario: A payload with no comment
- **WHEN** a test validates an `issues` payload that holds no comment
- **THEN** the payload holds no comment and the fields of the issue event validate as before

### Requirement: The consumer refuses a comment it does not trust
The roadmap consumer SHALL refuse an `issue_comment` delivery before any GitHub request when its action is not `created`, when its sender login is the Service bot or ends with `[bot]`, when the issue carries a pull request marker, or when `comment.author_association` is outside `CONST_ROADMAP_TRUSTED_AUTHORS`. It SHALL answer the first three with `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the untrusted author with `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, which counts as `ignored`.

#### Scenario: A non-created comment
- **WHEN** a test delivers a signed `issue_comment` payload whose action is `edited` or `deleted`
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

#### Scenario: A bot comment
- **WHEN** a test delivers a signed `issue_comment` payload whose sender login is the Service bot or ends with `[bot]`
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

#### Scenario: An untrusted author comment
- **WHEN** a test delivers a signed `issue_comment` payload whose `author_association` is outside `CONST_ROADMAP_TRUSTED_AUTHORS`
- **THEN** the route answers `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, counts the delivery as `ignored`, and the fake GitHub client records no request

#### Scenario: A pull request comment
- **WHEN** a test delivers a signed `issue_comment` payload whose issue carries a `pull_request` marker
- **THEN** the route answers `CONST_SERVICE_STATUS_COMMENT_REFUSED` and the fake GitHub client records no request

### Requirement: The roadmap consumer writes the cached issue before it wakes the lane
The roadmap consumer MUST write the issue of a subscribed `issues` event into the project brain from the event payload before it enqueues the wake of a row, and MUST send no GitHub request for that write.

#### Scenario: A labeled issue event writes the entry and wakes the row
- **WHEN** The roadmap consumer receives an `issues` event with action `labeled` for an issue of a Service repository.
- **THEN** The fake tier holds the new label set with the event time, and the fake lane trigger records one wake for the due row.

### Requirement: The payload holds the release fields
The model `GitHubWebhookPayload` SHALL parse the optional `release` object of a `release` delivery into `WebhookRelease`, with the fields `tag_name`, `html_url`, `body`, `draft`, `prerelease` and `published_at`. `published_at` SHALL be optional, so a delivery of a draft still validates and reaches the refusal instead of answering 400. The model SHALL ignore every other field of the release object.

#### Scenario: A published release payload parses
- **WHEN** a test validates a `release` payload with the action `published` and the six release fields
- **THEN** the payload release holds the tag, the URL and the body, and `draft` and `prerelease` are false

### Requirement: The consumer refuses an unwanted release delivery
The roadmap consumer SHALL refuse a `release` delivery before any GitHub request when its action is not `published`, when the release is a draft, when it is a prerelease, or when it carries no publication time. It SHALL answer each with `CONST_SERVICE_STATUS_RELEASE_REFUSED`, which counts as `ignored`, and SHALL queue no round and no scoped update.

#### Scenario: An unwanted release is refused
- **WHEN** a test sends a signed `release` delivery with the action `created`, one of a draft, one of a prerelease and one whose release holds no publication time
- **THEN** each delivery is answered with `CONST_SERVICE_STATUS_RELEASE_REFUSED`, the lanes queue no round, and the fake GitHub client records no request

### Requirement: Own-write issue deliveries refresh the cached issue without waking a lane
When `roadmap_consumer` refuses an `issues` delivery with `CONST_SERVICE_STATUS_OWN_WRITE` because its sender is the App bot, it SHALL refresh the `brain-issue` entry from `payload.issue` whenever no entry exists, the stored entry has no `updated_at`, or `payload.issue.updated_at` is strictly greater than the stored `updated_at`, while still returning `CONST_SERVICE_STATUS_OWN_WRITE`, counting outcome `self`, making no GitHub request, and waking no lane or scoped update.

#### Scenario: A newer own-write issue webhook updates the brain entry
- **WHEN** `valkey-devops` holds an issue cached at `T0` with `Status: In Progress`, and an App-bot `issues` webhook arrives for that issue with `updated_at` at `T1 > T0` and `Status: In Review`
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}`, counts outcome `self`, wakes no lane, and updates `valkey-devops` to `Status: In Review`

#### Scenario: A stale or same-second own-write webhook does not clobber a fresher cached entry
- **WHEN** `valkey-devops` holds an issue cached at `T1`, and an App-bot `issues` webhook arrives with `updated_at <= T1` (or with `comment` present or `pull_request` set)
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}` and keeps the existing brain entry unchanged

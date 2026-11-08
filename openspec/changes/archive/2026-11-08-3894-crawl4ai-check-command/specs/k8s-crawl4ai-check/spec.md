## Purpose
`devops k8s crawl4ai-check` tests a running Crawl4AI service for the controls that keep it off internal addresses: the refusal of an internal target on each route, the bearer token, and the NetworkPolicy of the pod. A person runs it again at each bump of the pinned image.

## ADDED Requirements

### Requirement: Dry run
The command SHALL print each request that it would make and MUST make no request, start no process and read no keyring with `--dry-run`.

#### Scenario: Dry run lists the requests
- **WHEN** a person runs `devops k8s crawl4ai-check --dry-run` with the process and HTTP fakes installed
- **THEN** the output lists the port-forward, a request for each route and target role, the requests without the token and the `kubectl run`, and the process fake and the HTTP fake record no call.

### Requirement: Route and target matrix
The command SHALL send one request with the token to each of the routes `/md`, `/html`, `/screenshot`, `/pdf` and `/llm/{url}` for each of the five internal target roles: the metadata address, loopback, the Kubernetes API Service, Service `crawl4ai` and Service `roadmap-service`.

#### Scenario: Twenty-five cases
- **WHEN** the command runs and the service refuses each target
- **THEN** the HTTP fake records 25 requests with the token, one for each route and target role, and the command exits 0.

### Requirement: Refusal of an internal target
The command MUST count a status of 400 or 403 with a body that is a JSON object with the one key `detail` as a refusal, and MUST exit 1 on any other answer.

#### Scenario: A served page
- **WHEN** the service answers one route and target with status 200 and page text
- **THEN** the command exits 1 and the report names that route and target role.

#### Scenario: A fault
- **WHEN** the service answers one route with status 500
- **THEN** the command exits 1, because a fault is no refusal.

### Requirement: Missing token
The command MUST send one request to each route without the token, and one to `/health`, and MUST require a refusal with status 401 or 403 on every route except `/health`.

#### Scenario: No token header
- **WHEN** the service answers 401 to each route without the header and 200 to `/health`
- **THEN** the command exits 0, and the same run exits 1 when `/md` answers 200 without the header.

### Requirement: Token from the keyring
The command MUST read the token from the keyring entry `crawl4ai_api_token`, MUST NOT print it or pass it on a command line, and MUST stop before it starts a process or sends a request when the entry is absent.

#### Scenario: Keyring entry absent
- **WHEN** the keyring holds no `crawl4ai_api_token` entry
- **THEN** the command exits 1 with a message that names `crawl4ai_api_token`, and the process fake and the HTTP fake record no call.

### Requirement: Forward to the service
The command SHALL forward a local port to Service `crawl4ai` in namespace `devops`, SHALL send every request through that forward, SHALL stop the forward when it ends, and MUST stop before it sends a request with the token when the forward ends at once or `/health` gives no answer.

#### Scenario: The forward ends at once
- **WHEN** the process fake answers the forward with a child that has ended
- **THEN** the command exits 1 and the HTTP fake records no request.

### Requirement: NetworkPolicy layer
The command SHALL start a throwaway pod that carries the label `app.kubernetes.io/name=crawl4ai` in namespace `devops`, SHALL report a destination as `blocked` or `reached` for the metadata address and for a private ClusterIP, SHALL exit 1 when the pod reaches a destination, and SHALL delete the pod after the probes.

#### Scenario: The pod cannot connect
- **WHEN** each connection probe of the pod fails
- **THEN** the report holds one `blocked` row for the metadata role and one for the private ClusterIP role, the command exits 0, and the last `kubectl` call deletes the pod.

#### Scenario: The pod connects
- **WHEN** the connection probe of the metadata address succeeds
- **THEN** the command exits 1, the report names the metadata role as `reached`, and the pod is deleted.

### Requirement: Throwaway pod
The throwaway pod SHALL meet Pod Security `restricted` and SHALL use an image pinned by digest. It MUST carry a readiness probe that always fails, so that Service `crawl4ai` never sends it traffic. The probe code SHALL be shared with other service checks and SHALL take the namespace, the labels and the targets as arguments.

#### Scenario: Pod spec
- **WHEN** the probe module starts the pod
- **THEN** `kubectl run` carries the labels and the namespace of the caller, an image with a digest, a non-root user, no privilege escalation, no capability, the `RuntimeDefault` seccomp profile and a readiness probe that runs `false`.

#### Scenario: A pod that fails to start
- **WHEN** `kubectl run` fails
- **THEN** the probe raises `ServiceProbeError` with the error of `kubectl`, and the pod is deleted.

### Requirement: Pinned image
An offline check of the `k8s` row of `devops ci` MUST compare the image of Deployment `crawl4ai` with the image that the command names.

#### Scenario: Image bump
- **WHEN** the Deployment pins an image that differs from `CRAWL4AI_IMAGE`
- **THEN** the check fails, names both images and the command that a person runs again.

### Requirement: Roles in the output
The command module and its output MUST name each target by a role and MUST NOT hold a private host name or a private address.

#### Scenario: Report rows
- **WHEN** the command runs for all 25 cases and the pod probes
- **THEN** the output holds one row for each route and target role with its status and the length of its body, each target appears as a role such as `<crawl4ai-service>`, and no row holds a metadata address, a cluster host name or a ClusterIP.

### Requirement: Hermetic tests
The tests of the command and of the probe MUST run with the process, HTTP and keyring fakes and MUST NOT skip on the state of the host.

#### Scenario: No cluster
- **WHEN** the suite runs on a host with no cluster and no keyring entry
- **THEN** each test of the command runs to a pass or a fail, none skips, and no test opens a socket or reads the OS keyring.

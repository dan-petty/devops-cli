## Purpose
`devops k8s searxng-check` tests a running SearXNG service for the points that a digest bump can change: the keys of the JSON reply, the categories of the kept engines, the handling of a query that starts with `!`, the engines that must stay off, and the NetworkPolicy peers of the pod. A person runs it again at each bump of the pinned image.

## ADDED Requirements

### Requirement: Dry run
The command SHALL print each call that it would make and MUST make no request and start no process with `--dry-run`.

#### Scenario: Dry run lists the calls
- **WHEN** a person runs `devops k8s searxng-check --dry-run` with the process and HTTP fakes installed
- **THEN** the output lists the port-forward, a line for each of the six search rows, the `kubectl run` of the throwaway pods and the connects, and the process fake and the HTTP fake record no call.

### Requirement: Search rows
The command SHALL send one `GET /search` request with `format=json` for each of the rows `json-general`, `json-it`, `json-science`, `bang-off-engine`, `bang-external` and `unused-category`, and SHALL send every request through the local forward and with no credential. The categories of the three `json-` rows MUST be those of `DEFAULT_SEARXNG_CATEGORIES`.

#### Scenario: Six requests
- **WHEN** the command runs against a service that answers each row as the pinned image does
- **THEN** the HTTP fake records six requests to `/search`, all to the local forward, all with `format=json`, none with an `Authorization` header, and the command exits 0.

### Requirement: Reply keys
The command MUST fail a `json-` row whose reply lacks one of the keys `answers`, `corrections`, `infoboxes`, `query`, `results`, `suggestions` and `unresponsive_engines`, or whose `unresponsive_engines` is not a list, and the output MUST name the key.

#### Scenario: A key is missing
- **WHEN** the service leaves `corrections` out of a reply
- **THEN** the command exits 1 and the output names `corrections`.

#### Scenario: Unresponsive engines is a string
- **WHEN** the service gives a string for `unresponsive_engines`
- **THEN** the command exits 1 and the output names `unresponsive_engines`.

### Requirement: Kept categories
The command MUST fail the `json-` row of a category in `DEFAULT_SEARXNG_CATEGORIES` that returns no hit, and the output MUST name the category.

#### Scenario: A category has no hit
- **WHEN** the service returns no hit for the category `science`
- **THEN** the command exits 1 and the output names `science`.

### Requirement: Format json
The command MUST fail a `json-` row that gets HTTP 403, and the output MUST name `search.formats`.

#### Scenario: Json is not a format
- **WHEN** the service answers the JSON requests with HTTP 403
- **THEN** the command exits 1 and the output names `search.formats`.

### Requirement: Engines that stay off
The command MUST fail a row whose reply names an engine that must stay off in `results` or in `unresponsive_engines`. The engines are `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`, matched as a prefix. The output MUST name the engine.

#### Scenario: A keyed engine is on
- **WHEN** a reply holds a hit whose engine is `google`
- **THEN** the command exits 1 and the output names `google`.

#### Scenario: A suspended engine is listed as unresponsive
- **WHEN** `unresponsive_engines` of a reply holds the engine `bing`
- **THEN** the command exits 1 and the output names `bing`.

### Requirement: Bang that names an engine that is off
The command SHALL send a query that starts with `!` and the name of an engine that the ConfigMap leaves off, and MUST fail the row `bang-off-engine` when the status is not 200 or when the reply holds a hit of that engine.

#### Scenario: The bang stays text
- **WHEN** the service answers the query with HTTP 200 and hits of kept engines only
- **THEN** the row `bang-off-engine` passes.

#### Scenario: The bang selects the engine
- **WHEN** the service answers the query with a hit of the engine that is off
- **THEN** the command exits 1 and the output names that engine.

### Requirement: External bang is not followed
The command SHALL send a query that starts with `!!`, MUST NOT follow a redirect, MUST send no request to the address of a `Location` header, and SHALL record the status of the answer. The row MUST fail on a status of 500 or more and on no answer.

#### Scenario: Redirect is not followed
- **WHEN** the service answers the query with HTTP 302 and a `Location` header
- **THEN** the report holds the status 302 for the row `bang-external`, the HTTP fake records no request to the `Location` address, and the command exits 0.

### Requirement: Category that no kept engine serves
The command SHALL send a request with a category that no kept engine serves, SHALL record its status and its number of hits, and MUST fail the row on a status of 500 or more or on no answer.

#### Scenario: Unused category
- **WHEN** the service answers the unused category with HTTP 200 and one hit
- **THEN** the report holds one row `unused-category` with the status 200 and the count 1, and the command exits 0.

### Requirement: Forward to the service
The command SHALL forward a local port to Service `searxng` in namespace `devops`, SHALL wait for `/healthz`, SHALL stop the forward when it ends, and MUST stop before it sends a search request when the forward ends at once or `/healthz` gives no answer. The code of the forward and of the pods SHALL be the code of `src/devops_cli/k8s/service_probe.py`, and the command module MUST define no second copy.

#### Scenario: The forward ends at once
- **WHEN** the process fake answers the forward with a child that has ended
- **THEN** the command exits 1 with a stated reason and the HTTP fake records no request.

#### Scenario: Health gives no answer
- **WHEN** `/healthz` gives no answer
- **THEN** the command exits 1, sends no search request and stops the forward.

### Requirement: NetworkPolicy peers
The command SHALL start a throwaway pod with a neutral label that is not the label of a client of the service, and MUST fail when it connects to port 8080 of Service `searxng`. It SHALL start a throwaway pod with the label `app.kubernetes.io/name=searxng`, and MUST fail when it connects to the metadata address or to the ClusterIP of Service `roadmap-service`. It SHALL delete each pod after its probes.

#### Scenario: Both pods are blocked
- **WHEN** each connect probe of each pod fails
- **THEN** the report holds three `blocked` rows, the command exits 0, and the last `kubectl` call deletes a pod.

#### Scenario: The unlabeled pod connects
- **WHEN** the connect from the pod with the neutral label to port 8080 succeeds
- **THEN** the command exits 1, the report names the unlabeled pod and the service as `reached`, and the pods are deleted.

#### Scenario: The labeled pod reaches the metadata address
- **WHEN** the connect from the pod with the label of `searxng` to the metadata address succeeds
- **THEN** the command exits 1 and the report names the SearXNG pod and the metadata role as `reached`.

### Requirement: Pinned image
An offline check of the `k8s` row of `devops ci` MUST compare the image of Deployment `searxng` with the image that the command names.

#### Scenario: Image bump
- **WHEN** the Deployment pins an image that differs from `SEARXNG_IMAGE`
- **THEN** the check fails, names both images and the command that a person runs again.

### Requirement: Roles in the output
The command and its output MUST name each pod and each target by a role and MUST NOT hold a private host name or a private address.

#### Scenario: Report rows
- **WHEN** the command runs for all rows
- **THEN** each pod and target appears as a role such as `<unlabeled-pod>`, `<searxng-pod>`, `<searxng-service>`, `<metadata>` or `<private-cluster-ip>`, and no row holds a metadata address, a cluster host name or a ClusterIP.

### Requirement: Context
The command SHALL pass `--context` to every `kubectl` call.

#### Scenario: Context option
- **WHEN** a person runs the command with `--context test-ctx`
- **THEN** every recorded `kubectl` call names the context `test-ctx`.

### Requirement: Reply fixture from the pinned image
The reply fixture of the SearXNG provider tests SHALL be a reply that the pinned image gave, and a file next to it SHALL name that image.

#### Scenario: Fixture names the image
- **WHEN** a test reads the fixture and `SEARXNG_IMAGE`
- **THEN** the fixture holds the seven reply keys and the file next to it holds `SEARXNG_IMAGE`.

### Requirement: Hermetic tests
The tests of the command MUST run with the process and HTTP fakes and MUST NOT skip on the state of the host.

#### Scenario: No cluster
- **WHEN** the suite runs on a host with no cluster
- **THEN** each test of the command runs to a pass or a fail, none skips, and no test opens a socket.

## Purpose

How `devops k8s tunnel` keeps the local end of the Kubernetes API route at `k8s.<domain>` running: one detached `cloudflared access tcp` forward after an Access login, its record under the data directory, its stop, and a status that tells a listening port and an answering API server apart.

## ADDED Requirements

### Requirement: The hostname comes from a setting with no fallback
`devops k8s tunnel start` SHALL read the hostname from `k8s.tunnel_host`. When the setting is unset, the command SHALL fail with an error that names the setting, and SHALL start no process.

#### Scenario: The setting is unset
- **WHEN** `k8s.tunnel_host` is unset and `devops k8s tunnel start` runs
- **THEN** the command fails with an error that names `k8s.tunnel_host`, and no process starts

### Requirement: Start logs in, then starts one detached forward
`devops k8s tunnel start` SHALL run `cloudflared access login --quiet https://<host>` with the terminal attached, then SHALL start `cloudflared access tcp --hostname <host> --url <address>:<port>` in a session of its own, record its pid and start time under the data directory, and wait until the port accepts connections. When a recorded forward still runs, the command SHALL report it and SHALL start no other process.

#### Scenario: Start a forward
- **WHEN** `devops k8s tunnel start` runs with `k8s.tunnel_host` set and no forward recorded
- **THEN** the login runs first, the forward starts in its own session with the host and the port, its record is saved, and the command ends when the port accepts connections

#### Scenario: A forward already runs
- **WHEN** `devops k8s tunnel start` runs while the recorded forward runs
- **THEN** the command reports that forward and starts no process

#### Scenario: A dry run
- **WHEN** `devops k8s tunnel start --dry-run` runs
- **THEN** the command prints the commands it would run and starts no process

### Requirement: Start can add the tunnel context
`devops k8s tunnel start --context` SHALL add or update the kubeconfig cluster and context `<cluster>-tunnel`, with the server at the forward's address and port, the TLS server name `kubernetes.default.svc`, and the CA data and the user of the home context.

#### Scenario: Add the tunnel context
- **WHEN** `devops k8s tunnel start --context` runs with a home context whose cluster is `home` and whose user is `admin`
- **THEN** `kubectl config set-cluster home-tunnel` sets the server and the TLS server name, `kubectl config set clusters.home-tunnel.certificate-authority-data` sets the CA data of `home`, and `kubectl config set-context home-tunnel` names the cluster `home-tunnel` and the user `admin`

### Requirement: Stop ends the forward's process group
`devops k8s tunnel stop` SHALL signal the process group of the recorded forward through `terminate_process_group`, and SHALL remove the record.

#### Scenario: Stop a running forward
- **WHEN** `devops k8s tunnel stop` runs while the recorded forward runs
- **THEN** the forward's process ends and no record is left

### Requirement: Status tells the port and the API server apart
`devops k8s tunnel status` SHALL report whether the port accepts connections and, for the tunnel context, whether the API server answers `/version`. Any HTTP status SHALL count as an answer.

#### Scenario: The API server refuses the credential
- **WHEN** the port accepts connections and the API server of the tunnel context answers `/version` with 401
- **THEN** status reports the port as listening and the API server as answering

#### Scenario: Nothing listens
- **WHEN** no forward is recorded and nothing listens on the port
- **THEN** status reports no forward and the port as not listening

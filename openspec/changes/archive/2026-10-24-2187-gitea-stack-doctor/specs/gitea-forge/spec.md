## ADDED Requirements

### Requirement: The doctor reports each check of the Gitea stack
`devops k8s doctor --stack gitea` SHALL run the checks of the live Gitea stack in place of the cluster rules, and SHALL report the name, the resource, the result and the reason of each check, in order. A failed check SHALL NOT stop the next one. The command SHALL exit 2 when a check fails and 0 when every check passes.

#### Scenario: A healthy Gitea stack
- **WHEN** the process fake and the HTTP fake answer as a healthy Gitea stack
- **THEN** every check passes with its reason, and the command exits 0 with each check in its JSON output

#### Scenario: A failed check
- **WHEN** namespace `gitea` has the enforce level `baseline`
- **THEN** the table marks `pod-security-restricted` FAIL with the reason, and the command exits 2

### Requirement: The doctor checks the Gitea objects in the cluster
The checks SHALL read the cluster with kubectl, each object once, and SHALL pass when Applications `gitea` and `gitea-manifests` are `Synced` and `Healthy`, the volume of claim `gitea-shared-storage` has the reclaim policy `Retain`, namespace `gitea` has the Pod Security enforce level `restricted`, Ingress `gitea/gitea-ingress` has a host that is not `git.example.com`, and `curl https://github.com` in the Gitea container exits 7 or 28.

#### Scenario: One broken object
- **WHEN** one Application, the claim, the volume, the namespace, the Ingress or the egress probe is wrong, or kubectl cannot read an object
- **THEN** only its own check fails, with the reason or kubectl's error

### Requirement: The doctor checks Gitea through the host of the live Ingress
The checks through the host SHALL send each request through the egress-checked client to the host of the live Ingress only, and SHALL pass when `GET /user/login` answers 200, `GET /api/v1/repos/search` with no sign-in answers 401 or 403, and `GET /v2/` answers 401 with a Bearer challenge whose realm is an HTTPS URL on the host. When the Ingress gives no host, these checks and the clone-URL check SHALL fail with `not run` and SHALL send no request.

#### Scenario: One wrong answer
- **WHEN** the sign-in page redirects, the anonymous read answers 200, or the registry gives no Bearer challenge or a realm under another host
- **THEN** only its own check fails, with the reason

#### Scenario: The Ingress gives no host
- **WHEN** the Ingress has no host, or has `git.example.com`
- **THEN** `ingress-host` and the four checks through the host fail, and no HTTP request is sent

### Requirement: The clone-URL check uses a temporary private repository
The check SHALL read the password of `gitea_admin` at run time through the settings layer (`gitea.admin_password`, keyring key `gitea_admin_password`), SHALL make the private repository `devops-doctor-<random>` with `POST /api/v1/user/repos`, and SHALL pass when its `clone_url` is an HTTPS URL on the host and its `ssh_url` does not name the host. Without a password, or when the configuration does not load, it SHALL fail with the reason and send no create.

#### Scenario: The clone URL is wrong
- **WHEN** `clone_url` is under another host, or `ssh_url` names the host
- **THEN** `clone-url` fails with the URL

#### Scenario: The keyring holds no password
- **WHEN** the keyring holds no `gitea_admin_password`
- **THEN** `clone-url` fails and names `devops config set gitea.admin_password`, and no create is sent

#### Scenario: The configuration does not load
- **WHEN** the configuration holds a key that the settings refuse
- **THEN** `clone-url` fails and names the key, no create is sent, and the other checks report

### Requirement: The doctor deletes the temporary repository
The doctor SHALL send `DELETE /api/v1/repos/gitea_admin/<name>` whenever Gitea can hold the repository: after a 201, also when the clone-URL check fails after it, and when the create gets no answer. It SHALL send no delete when Gitea refuses the create. A delete that does not answer 204 or 404 SHALL fail `temporary-repository-deleted` and name the repository.

#### Scenario: The clone-URL check fails
- **WHEN** the clone-URL check fails after a 201
- **THEN** the delete is sent, `temporary-repository-deleted` passes, and Gitea holds no repository

#### Scenario: The create gets no answer
- **WHEN** the create times out
- **THEN** `clone-url` fails with the error, and the delete is sent

#### Scenario: Gitea refuses the create
- **WHEN** the create answers 422
- **THEN** `clone-url` fails with Gitea's message, and no delete is sent

#### Scenario: The delete fails
- **WHEN** the delete answers 500
- **THEN** `temporary-repository-deleted` fails and names the repository to delete by hand

### Requirement: The admin password stays in the Authorization header
The password SHALL go only into the Authorization header of the create and the delete, and into no argument list, log record, output or reason.

#### Scenario: A run with JSON output
- **WHEN** the command runs with JSON output
- **THEN** no output, log record, kubectl argument list or printed request holds the password or its Basic token, and only the create and the delete carry the Authorization header

### Requirement: The dry run of the Gitea checks makes no request
`devops k8s doctor --stack gitea --dry-run` SHALL list each kubectl command and each HTTP request in order, with placeholders for the host, the volume, the password and the repository name, and SHALL start no program, send no request and read no keyring entry. `--stack` SHALL accept only `gitea`.

#### Scenario: A dry run
- **WHEN** `devops k8s doctor --stack gitea --dry-run --context lab` runs
- **THEN** it prints the twelve requests, the body of the create among them, and the process fake, the HTTP fake and the keyring record nothing

#### Scenario: Another stack
- **WHEN** `devops k8s doctor --stack llm` runs
- **THEN** it exits 2 with a usage error, and starts no program

# Design

## Context

`devops k8s doctor` reads nodes, pods and warning events through the Kubernetes API and ranks findings with a fixed rule table. A finding is a problem, so the report has no place for a check that passed. The Gitea stack needs a set of checks that each pass or fail, and some of them go through the Cloudflare tunnel to Gitea and make a temporary repository.

## Decisions

### A `--stack` scope of the doctor

`--stack gitea` runs the stack's checks in place of the cluster rules, and the report holds them in the new field `checks`. Each `DoctorCheck` has a name, the resource it reads, the result and the reason. The command exits 2 when a check fails, as it does for a finding, and 0 when every check passes. `--stack` accepts only the stacks in `CONST_K8S_DOCTOR_STACKS`, today `gitea`.

Rejected: run the Gitea checks in every `devops k8s doctor`. They write to Gitea and need the admin password, and a cluster diagnosis must not do either. Rejected: a new command such as `devops k8s gitea check`. The issue names the doctor, and the doctor is the diagnosis command.

### kubectl for the cluster reads

The checks read the cluster with kubectl through `run_subprocess`, as `secret_push.py` and `node_port.py` do. The egress probe needs `kubectl exec`, and the Application is a custom resource, so one edge (kubectl, faked by `ProcessFake`) covers every read. The argument lists live in one function each, which both the run and the dry-run plan use, so the plan names the commands that the run starts.

Rejected: the Kubernetes Python client of the cluster rules. Its exec goes through `kubernetes.stream`, a websocket, and the Application needs `CustomObjectsApi`: two more edges for the tests to fake.

### The host comes from the live Ingress

git holds the placeholder host `git.example.com` (#1290), and deploy-stack sets the configured domain on the live Ingress. The checks read the host from the live Ingress. When it has no host, or still has the placeholder, `ingress-host` fails, and the four checks through the tunnel fail with `not run: <reason>` and send nothing.

### The temporary repository

The clone-URL check reads the password, then makes `devops-doctor-<8 hex digits>` with `POST /api/v1/user/repos` (private, not initialized, with a description that names the doctor). A record of the repository holds whether Gitea can hold it: from the send of the create on, until Gitea refuses the create. A `finally` block sends the delete whenever Gitea can hold it, so the delete goes out after a 201, when a later step of the check fails, when the create gets no answer, and when an error that the check does not catch stops it. A refused create (400, 409, 422 or a refused sign-in) made nothing, and a 409 means that another repository has the name, so no delete goes out. A delete that answers 204 or 404 passes `temporary-repository-deleted`. Another answer fails it and names the repository, so that a person can delete it.

### The SSH URL

Gitea v1.27.3 fills `ssh_url` also when SSH is off (Feasibility), so "no SSH URL" cannot hold. The check reads the host of `ssh_url` with `urlsplit`, after it puts `ssh://` before git's scp-like form `user@host:path` (git-clone(1), GIT URLS), and fails when that host is the tunnel host, which carries no SSH.

### The token challenge

`GET /v2/` must answer 401 with a Bearer challenge (RFC 6750) whose realm is an HTTPS URL on the tunnel host. The check reads each `WWW-Authenticate` header and parses the parameters with the standard `parse_http_list` and `parse_keqv_list`. A realm under the in-cluster address shows that Gitea did not get the forwarded host and protocol.

### The password

The password comes from `get_gitea_admin_password`, which resolves the managed option through the one provider chain. It goes into an `httpx2.BasicAuth`, which a field with `repr=False` holds, and httpx2 shows the Authorization header as `[secure]` in the repr of the headers. No argument list, log line or reason holds it. Each reason goes through `mask_secrets`, because a reason can quote kubectl or Gitea.

A configuration that the settings refuse makes `load_settings` raise an error. For an unknown key, it is a `ConfigurationError` that names the file, the line and the command that removes the key (#2207), and the clone-URL check fails with that message. For another refused value, it is a pydantic `ValidationError`, and the clone-URL check fails with the location and the message of the first error, read with `include_input=False` so that no configured value reaches the reason. In both cases the other checks still report. Without this, the error stopped the whole command with a traceback in the live run.

### The egress probe

`curl -sS -m 5 -o /dev/null https://github.com` runs in the Gitea container. Exit 7 (failed connect) or 28 (timeout) passes. Exit 0 fails: the pod reached the internet. Another exit fails with the first line of the error. Exit 6 (no name resolution) fails too: the perimeter admits DNS, so a failed lookup shows a different fault, not the perimeter.

Rejected: `kubectl label --dry-run=server` on the namespace for Pod Security, which the hand-run check used. It is a write call with `dryRun`, and its answer is warning text to parse. The check reads the enforce label. The namespace has had it since it was made (`k8s/namespaces.yaml`), so admission has refused every pod that is not `restricted`.

### The MCP annotation

The MCP tool `k8s_doctor` gets `readOnlyHint: false`, because the `stack` parameter makes a repository. `tests/test_fastmcp_contracts.py` (#857) holds a tool that writes under one of its arguments to `false`.

### The shared HTTP fake

`StubWeb.serve` adds a server that answers a request by its method, path and body, before the routes. The test's `GiteaServer` makes a repository under the name in the body of the create, and serves the delete of that name, so a test reads the random name from the recorded create.

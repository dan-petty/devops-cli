# Proposal

## Why

Issue #2187: after the Gitea stack (#1081) was deployed on 2026-10-24, its checks were curl and kubectl lines from the pull request body that a person ran by hand: the tunnel host answers, an anonymous API read is refused, the clone URL of a repository names the public host (this needs the admin password and a test repository), the pod has no internet egress, and the namespace has Pod Security `restricted`. The owner's paste of one of them failed on a placeholder. The owner (2026-10-24): "most of this should be managed with infra code and devops cli functionality".

## What Changes

- `devops k8s doctor` gets the option `--stack`, with the one value `gitea`. `--stack gitea` runs the checks of the live Gitea stack in place of the cluster rules, and reports the result and the reason of each check: Applications `gitea` and `gitea-manifests` are `Synced` and `Healthy`; the volume of claim `gitea-shared-storage` has the reclaim policy `Retain`; namespace `gitea` has the Pod Security enforce level `restricted`; Ingress `gitea/gitea-ingress` has a host that is not the placeholder in git; through that host, the sign-in page answers 200, an anonymous `GET /api/v1/repos/search` answers 401 or 403, and `GET /v2/` answers 401 with a Bearer challenge under the host; a temporary private repository has a `clone_url` under `https://<host>/` and an `ssh_url` that does not name the host; Gitea deletes the repository; and the pod cannot connect to `https://github.com`. The command exits 2 when a check fails. `--dry-run` lists the kubectl commands and the HTTP requests, and makes none of them.
- The new module `src/devops_cli/k8s/gitea_doctor.py` holds the checks. kubectl runs through `run_subprocess` (`devops_cli.core.process`), and the HTTP requests go through `new_http_client` (`devops_cli.http.client`) at egress level `public`. The host comes from the live Ingress, not from git.
- The clone-URL check reads the admin password at run time through the settings layer (`get_gitea_admin_password`, the managed option `gitea.admin_password`, keyring key `gitea_admin_password`). The password goes only into the Authorization header of the create and the delete. The check deletes the repository whenever Gitea can hold it: after a 201, also when the check fails, and when the create gets no answer.
- `DoctorReport` gets `checks`, a list of `DoctorCheck` (name, resource, passed, reason). `DoctorCheckError` carries the reason of a failed check. The admin user `gitea_admin` becomes the constant `CONST_K8S_GITEA_ADMIN_USER`, which the push-secrets row `gitea/gitea-admin` uses too.
- The MCP tool `k8s_doctor` gets the parameter `stack` and the annotation `readOnlyHint: false`, because `stack` makes a temporary repository.
- The shared HTTP fake `StubWeb` (`tests/web_fakes.py`) gets `serve`, a server that answers by method and body, because the delete goes to a name that only the run knows.
- `k8s/README.md`, Gitea: rollout step 5 names the command, and the section `Stack checks` lists each check. The knowledge base task `k8s_stack_deployment.md` names the command. The command, MCP and error documents are regenerated.
- The option, its output and its exit codes are observable behavior, so the change has a spec delta: added requirements in `gitea-forge`.
- This change fits in one pull request: one module, one option, one model field and their tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gitea-forge`: added requirements for the checks of the live stack that `devops k8s doctor --stack gitea` runs.

## Impact

- `src/devops_cli/k8s/gitea_doctor.py` (new), `src/devops_cli/commands/k8s/diagnostics.py`, `src/devops_cli/models/k8s.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_gitea_doctor.py` (new), `tests/web_fakes.py`.
- `k8s/README.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`, `docs/MCP_TOOLS.md` and `docs/ERRORS.md`.
- A run of `--stack gitea` makes one private repository `devops-doctor-<random>` in Gitea for a short time, as `gitea_admin`.

## Feasibility

Checked on 2026-10-24 against the repository at `22e5a166`, the Gitea v1.27.3 source, and read-only commands on the homelab cluster (Gitea 1.27.3, image `docker.gitea.com/gitea:1.27.3-rootless`):

- **Cluster.** Applications `gitea` and `gitea-manifests` are `Synced` and `Healthy`. Claim `gitea-shared-storage` is bound, and its volume has the reclaim policy `Retain`. Namespace `gitea` has the labels `pod-security.kubernetes.io/enforce`, `warn` and `audit` set to `restricted`. Ingress `gitea/gitea-ingress` has one rule, with the configured domain as host (deploy-stack's patch, #1290), to Service `gitea-http` port 3000.
- **Tunnel host, with no sign-in.** `GET /user/login` answers 200. `GET /api/v1/repos/search` answers 403 with `{"message":"Only signed in user is allowed to call APIs."}`. `GET /v2/` answers 401 with two challenges: `Bearer realm="https://git.<domain>/v2/token",service="container_registry",scope="*"` and `Basic realm="Gitea Container Registry"`.
- **Egress.** The image is Alpine and holds curl, wget and nc. `kubectl -n gitea exec deploy/gitea -c gitea -- curl -sS -m 5 -o /dev/null https://github.com` exits 7 at once (`Failed to connect to github.com:443 ... Could not connect to server`), and kubectl gives the exit code of the command. curl's man page names exit 7 as a failed connect and 28 as a timeout.
- **SSH URL.** The issue asks for "no SSH URL". Gitea v1.27.3 always fills `ssh_url`: `services/convert/repository.go` sets `SSHURL: cloneLink.SSH` from `repo.CloneLinkGeneral`, and `ComposeSSHCloneURL` in `models/repo/repo.go` does not read `DISABLE_SSH`. The live `app.ini` has `DISABLE_SSH = true`, `START_SSH_SERVER = false`, `SSH_PORT = 22` and `SSH_DOMAIN = gitea-http.gitea.svc.cluster.local`, so `ssh_url` is `<user>@gitea-http.gitea.svc.cluster.local:<owner>/<name>.git`, where nothing answers. So the check passes when `ssh_url` does not name the tunnel host, which carries no SSH. A live run of the check gave `ssh_url` `git@gitea-http.gitea.svc.cluster.local:gitea_admin/<name>.git`. `clone_url` comes from `ComposeHTTPSCloneURL` with `httplib.GuessCurrentAppURL`, the host and protocol of the request (#1081).
- **API.** In the v1.27.3 swagger, `POST /user/repos` takes `CreateRepoOption` (`name`, `private`, `auto_init`, `description`) and answers 201 with a `Repository` (`clone_url`, `ssh_url`), or 400, 409 or 422. `DELETE /repos/{owner}/{repo}` answers 204, 403 or 404. A 409 means that a repository of that name exists already, so the check sends no delete after a refused create. `modules/setting/service.go` defaults `ENABLE_BASIC_AUTHENTICATION` to true, and `k8s/gitea/values.yaml` does not change it, so the admin signs in with Basic authentication.
- **Password.** `gitea.admin_password` is a managed secret option with keyring key `gitea_admin_password` and the variable `DEVOPS_CLI_GITEA_ADMIN_PASSWORD` (#1081). `_resolve` in `src/devops_cli/config/settings.py` reads it through the one provider chain: keyring, Vault, environment, configuration.
- **Configuration.** Since #2168, the settings refuse an unknown key of section `ai`. Since #2207, `load_settings` raises a `ConfigurationError` for an unknown key, which names its file, its line and the command that removes it, and a pydantic `ValidationError` for another refused value. The clone-URL check reports the `ConfigurationError` message, or the location and the message of the first validation error (`errors(include_input=False)`, so no value), and the other checks still run.
- **Tests.** `ProcessFake` matches kubectl by its argument prefix. `StubWeb` answered by URL only, and the delete goes to a random name, so it gets `serve`. The test configuration sets `k8s.context`, so the command tests pass `--context`.

## Existing Tool Considered

- **Gitea's `gitea doctor check`**, in the image, checks the database, the repositories and the configuration from inside the pod. It does not check what a workstation gets through the tunnel: the sign-in page, the refusal of an anonymous read, the token realm and the clone URL. It does not check the perimeter either.
- **A network policy tester**, such as netassert, starts its own pods to probe the policies. The one probe here is one curl in the Gitea container, which the image holds.
- **The Argo CD CLI** (`argocd app get`) needs a session. kubectl reads the same status from the Application resource.
- The checks use kubectl, httpx2 through the project's client factory, and the standard parsers `urllib.parse.urlsplit` and `urllib.request.parse_http_list` and `parse_keqv_list` for the URLs and the challenge. No open tool runs this set of checks, so the change builds the glue: about 300k tokens to build, about 20k tokens a year to keep and fix as Gitea's API changes, and about two hours of elapsed time.

The change deletes no internal code. It replaces the hand-run lines of #1081, which are in its archived tasks only.

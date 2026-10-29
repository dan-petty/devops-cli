# Proposal

## Why

Issue #1822: `SandboxPolicy` cannot carry a seccomp profile, so each container sandbox runs under the default profile of its engine. #698 dropped the field on 2026-10-22 because no command built a policy that would use it, and because Podman read a profile in `HostConfig.SecurityOpt` as a file path. This change adds the field with the commands that set it, and sends the profile in the form that each engine reads.

## What Changes

- `devops sandbox deploy`, `devops docker sandbox` and `devops test sandbox` have the option `--seccomp-profile <file>`. The file has the JSON format of `docker --security-opt seccomp=<file>`.
- The command reads and checks the file before it does anything else, also in a dry run. The file must be a JSON object, and its `defaultAction` must refuse the system calls that the profile does not name. `SCMP_ACT_ALLOW` and `SCMP_ACT_LOG` let every call through, so they are refused. Each refusal is a `SandboxValidationError` that names the file, and the command stops with one error line.
- `SandboxPolicy.seccomp_profile` holds the checked profile: its absolute path and its compact JSON. It is `None` by default, and then the container runs under the engine's default profile, as before.
- The container gets one more `security_opt` entry, `seccomp=<compact JSON>`. A Podman engine older than 6.2.0 gets `seccomp=<absolute path>` instead. `DockerEngineService.accepts_inline_seccomp_profile` decides the form from the components that `GET /version` names, and it is asked only when the policy has a profile.
- The dry run of each command names the profile file in `seccomp_profile`. The dry run asks the engine nothing, so its declared controls show the inline form.
- The sandbox commands change behavior that a user sees, so the change carries a spec delta: the new capability `sandbox-seccomp-profile`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `sandbox-seccomp-profile`: how a container sandbox takes a seccomp profile from a file, how the file is checked, and the form in which each engine gets it.

## Impact

- `src/devops_cli/sandbox/seccomp.py` (new), `src/devops_cli/sandbox/models.py`, `src/devops_cli/sandbox/engine.py`, `src/devops_cli/docker/sandbox.py`, `src/devops_cli/docker/engine.py`.
- `src/devops_cli/commands/sandbox.py`, `src/devops_cli/commands/docker.py`, `src/devops_cli/commands/test_cmd.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_sandbox_seccomp.py` (new), and `set_podman` of `tests/support/fakes/docker_engine.py`, which now takes a version.
- The generated command reference, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- **Docker.** The docker CLI reads the profile file, compacts the JSON and sends `seccomp=<compact JSON>` in `HostConfig.SecurityOpt` (`parseSecurityOpts` in `cli/command/container/opts.go` of docker/cli, at commit `09d30a34bf`, 2026-09-03). docker-py 7.2.0, the locked SDK, copies `security_opt` into `HostConfig.SecurityOpt` unchanged (`docker/types/containers.py`), so the code must send the JSON itself.
- **Podman.** containers/podman#29726, "compat API: accept inline seccomp profiles", merged on 2026-09-24. Before it, the compat create endpoint read the value as a file path, and an inline profile failed with "file name too long". A path still works after it. The merge commit is in `v6.2.0-rc1` (2026-10-26), whose release notes name the change. The stable `v6.1.4` and `v5.8.9` (2026-10-12) are on branches that do not contain the commit (`compare` status `diverged`), and their notes do not name it. So Podman 6.2.0-rc1 and later get the JSON, and an older Podman gets the path.
- **Live check, Docker Engine 29.9.2 on this host.** The scratch profile was the default profile of moby/profiles (`seccomp/default.json` at `6fe7deb1b9fb`, Apache-2.0), with `chmod`, `fchmod`, `fchmodat` and `fchmodat2` removed from its allow list. It was not committed. `devops sandbox deploy --seccomp-profile <it>` started the sandbox, and the inspected container held `no-new-privileges:true` and `seccomp={"defaultAction":"SCMP_ACT_ERRNO",...}`. In it, `chmod 600 /tmp/x` and Python's `os.chmod` failed with "Operation not permitted". In a control sandbox without the option, both worked. Both sandboxes were removed.
- The engine on this host is Docker, so the Podman path form was checked only against the fake engine and the Podman pull request, not against a live Podman.

## Existing Tool Considered

The engines enforce the profile; devops-cli only reads a file in their format and passes it on, as the docker CLI and `podman run --security-opt` do. The check uses the standard library's `json`, and the version gate uses `packaging`, which is a direct dependency. No profile is written or shipped: the user gives one, for example the engine's own default profile with calls removed. The change deletes no code. The cost of what it builds is small: one 70-line module, one engine method and one option on three commands.

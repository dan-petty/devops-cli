# Design

## Decisions

### The profile is checked once, when the command reads its option

`load_seccomp_profile` reads the file, parses it with `json`, and returns a frozen `SeccompProfile` with the absolute path and the compact JSON. The three commands call it through `container_sandbox_policy`, before the dry run, so a bad file stops the command before any engine call. The error is a `SandboxValidationError`, which the exit seam of `new_typer()` reports as one line with its own exit status.

### A profile must refuse the calls that it does not name

A `defaultAction` of `SCMP_ACT_ALLOW` or `SCMP_ACT_LOG` lets every system call through. Such a profile confines only the calls that it names, which is a deny list, and the engines' own default profiles are allow lists (`SCMP_ACT_ERRNO`). The issue asked to refuse `SCMP_ACT_ALLOW`. `SCMP_ACT_LOG` also allows the call, so it is refused too.

### The declared controls stay pure, and the create step picks the form

`declared_controls` of both runners asks the engine nothing, so the dry run can show it. It renders the inline form by default. `_build_create_kwargs`, which calls the engine to create the container, asks `accepts_inline_seccomp_profile()` only when the policy has a profile, and passes the answer to `declared_controls`. A sandbox without a profile sends no extra request.

### The engine version comes from the components that `GET /version` names

`kind()` already read those components. They are now read once into the service's response cache, and both `kind()` and `accepts_inline_seccomp_profile()` read the cache. A Podman component whose version is 6.2.0rc1 or later takes the JSON. A Podman version that does not parse gets the path, because a path works on every Podman.

## Rejected alternatives

- **Always send the path.** Docker reads `seccomp=<value>` as the profile's JSON, so a path fails there (docker/cli `parseSecurityOpts` sends the content, never the path). It also fails on a remote Podman engine, which cannot read a file of the workstation.
- **Always send the JSON.** Every stable Podman release on 2026-10-29 (`v6.1.4`, `v5.8.9`) reads the value as a path and fails with "file name too long" (containers/podman#27710, fixed by #29726 in `v6.2.0-rc1`).
- **Ask the engine in `declared_controls`.** The dry run must make no request, and `declared_controls` is documented as pure.
- **Ship a profile with devops-cli.** The issue asks for a file that the user gives. The engines' default profiles already exist and change with each engine release. A copy in the repository would drift from the engine that runs it.
- **Check the profile against a JSON schema.** No maintained schema package for the seccomp profile format exists, and the engine checks the full format when it creates the container. The load checks only what makes a profile unsafe or unreadable.
- **A setting in `config.yaml`.** The issue asks for a per-command option, and a setting would apply one profile to every sandbox, also the review's tool sandbox, which is bubblewrap and has no seccomp option.

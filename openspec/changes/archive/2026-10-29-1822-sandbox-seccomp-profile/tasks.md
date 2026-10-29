# Tasks

## 1. A sandbox takes a checked seccomp profile, and each engine gets the form it reads

- [x] Add failing tests: the default policy declares no seccomp entry; a profile loads as its absolute path and compact JSON; a missing file, a non-JSON file, a JSON list, a file with no `defaultAction`, and a `defaultAction` of `SCMP_ACT_ALLOW` or `SCMP_ACT_LOG` are refused; the policy renders the inline and the path form; the engine takes the inline form on Docker and on Podman 6.2.0-rc1 and later; both runners create the container with the form that the engine takes; a sandbox with no profile asks the engine for no version; each of the three commands names the profile in its dry run and refuses a bad profile with one error line
  - Verification: `uv run devops ci test tests/test_sandbox_seccomp.py`
- [x] Add `sandbox/seccomp.py`, `SandboxPolicy.seccomp_profile`, `container_sandbox_policy`, `DockerEngineService.accepts_inline_seccomp_profile`, the `inline_seccomp` argument of both `declared_controls`, and `--seccomp-profile` on `sandbox deploy`, `docker sandbox` and `test sandbox`
  - Verification: `uv run devops ci test tests/test_sandbox_seccomp.py tests/test_sandbox_lifecycle.py tests/test_workload_sandbox.py tests/test_docker_engine.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1822-sandbox-seccomp-profile`
- Pending a person: run a sandbox with `--seccomp-profile` on a Podman engine, which this host does not have, and check that the container starts and refuses a call that the profile does not allow.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

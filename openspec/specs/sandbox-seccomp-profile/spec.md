# sandbox-seccomp-profile Specification

## Purpose
How a container sandbox runs under a seccomp profile from a file instead of the engine's default profile: the option that names the file, the checks of the file, and the form in which Docker and Podman get the profile.

## Requirements

### Requirement: The sandbox commands take a seccomp profile file
`devops sandbox deploy`, `devops docker sandbox` and `devops test sandbox` SHALL take `--seccomp-profile <file>`. Without the option, the container SHALL get no seccomp entry in `security_opt`, so it runs under the engine's default profile.

#### Scenario: No profile
- **WHEN** a sandbox policy names no profile
- **THEN** its `security_opt` is `["no-new-privileges:true"]`

#### Scenario: The dry run names the profile
- **WHEN** each of the three commands runs with `--seccomp-profile <file>` and `--dry-run`
- **THEN** it exits 0, sends nothing, and its output names the file's absolute path in `seccomp_profile`

### Requirement: A seccomp profile is checked before the command runs
The command SHALL refuse the profile file, with a `SandboxValidationError` that names the file and with no engine call, when the file cannot be read, is not JSON, is not a JSON object, names no `defaultAction` text, or has a `defaultAction` of `SCMP_ACT_ALLOW` or `SCMP_ACT_LOG`.

#### Scenario: A profile that allows every call by default
- **WHEN** a command gets a profile whose `defaultAction` is `SCMP_ACT_ALLOW`
- **THEN** it exits with the status of `SandboxValidationError`, prints that the profile allows every system call by default, and prints no traceback

#### Scenario: A file that is not a profile
- **WHEN** the file is missing, is not JSON, is a JSON list, or names no `defaultAction`
- **THEN** the load fails with a `SandboxValidationError` whose message names the file

### Requirement: Each engine gets the profile in the form that it reads
The container SHALL get `seccomp=<compact JSON of the profile>` after the policy's other `security_opt` entries. A Podman engine whose version is older than 6.2.0-rc1, or does not parse, SHALL get `seccomp=<absolute path of the file>` instead. The engine SHALL be asked for its version only when the policy has a profile.

#### Scenario: Docker
- **WHEN** a sandbox with a profile is created on a Docker engine
- **THEN** the create call has `security_opt` `["no-new-privileges:true", "seccomp=<compact JSON>"]`

#### Scenario: An older Podman
- **WHEN** a sandbox with a profile is created on Podman 6.1.4
- **THEN** the create call has `security_opt` `["no-new-privileges:true", "seccomp=<absolute path>"]`

#### Scenario: Podman 6.2
- **WHEN** the engine is Podman 6.2.0-rc1, 6.2.0 or later
- **THEN** the engine takes the inline JSON

#### Scenario: No profile, no version request
- **WHEN** a sandbox with no profile is deployed
- **THEN** the engine gets no `GET /version` request for the seccomp form

## ADDED Requirements

### Requirement: A caller override of an ssh key or of SHELL is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `SSH_`. It SHALL refuse `SHELL` in the same way. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: The askpass program
- **WHEN** a caller builds a child environment with the override `SSH_ASKPASS` or `SSH_ASKPASS_REQUIRE`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A security key library or helper, and a PKCS#11 helper
- **WHEN** a caller builds a child environment with the override `SSH_SK_PROVIDER`, `SSH_SK_HELPER` or `SSH_PKCS11_HELPER`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The agent socket and the agent process
- **WHEN** a caller builds a child environment with the override `SSH_AUTH_SOCK` or `SSH_AGENT_PID`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: An ssh key that no caller sets
- **WHEN** a caller builds a child environment with the override `SSH_ORIGINAL_COMMAND` or `SSH_EXAMPLE_KEY`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The shell that ssh starts
- **WHEN** a caller builds a child environment with the override `SHELL` or `shell`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A key that ssh reads but that runs no program reaches the child
`build_subprocess_env` SHALL put `DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `TMPDIR`, `LANG` and `HOME` of the caller override in the child environment with their values. It SHALL do the same for a key that starts with `SSH` and has no underscore after it. It SHALL do the same for a key that only contains a refused ssh name.

#### Scenario: Display, cookie, temporary directory, locale and home keys, and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `TMPDIR`, `LANG`, `HOME`, `SSHPASS` and `EXAMPLE_SSH_ASKPASS`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: An isolated child gets no SHELL from the environment
With isolation on, `build_subprocess_env` SHALL keep `SHELL` out of the child environment, in upper and lower case. This holds when the process environment holds the key and the caller names no `extra_allowed_keys`. With isolation off, the child gets the environment as it is.

#### Scenario: SHELL in the environment of the person
- **WHEN** the environment holds `SHELL`, and a caller builds a child environment with isolation on
- **THEN** the child environment holds no `SHELL`

#### Scenario: SHELL with isolation off
- **WHEN** the environment holds `SHELL`, and a caller builds a child environment with isolation off
- **THEN** the child environment holds `SHELL` with its value

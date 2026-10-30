## ADDED Requirements

### Requirement: A caller override of a key that makes gh or kubectl run a program is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` for a caller override whose upper-case key is `GH_BROWSER`, `BROWSER`, `GH_EDITOR`, `GH_PAGER`, `GH_PATH`, `KUBE_EDITOR` or `KUBECTL_EXTERNAL_DIFF`. It SHALL do this with environment isolation on and off.

#### Scenario: The browser, the editor and the pager of gh
- **WHEN** a caller builds a child environment with the override `GH_BROWSER`, `BROWSER`, `GH_EDITOR` or `GH_PAGER`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The path of the gh executable
- **WHEN** a caller builds a child environment with the override `GH_PATH` or `gh_path`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The editor and the diff program of kubectl
- **WHEN** a caller builds a child environment with the override `KUBE_EDITOR` or `KUBECTL_EXTERNAL_DIFF`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A refused key starts no child
- **WHEN** a caller runs a program with `run_subprocess` and the override `GH_BROWSER`
- **THEN** `run_subprocess` raises `SecurityError` and the program does not start

### Requirement: An isolated child gets no gh or kubectl program key from the environment
With isolation on, `build_subprocess_env` SHALL keep `GH_BROWSER`, `BROWSER`, `GH_EDITOR`, `GH_PAGER`, `GH_PATH`, `KUBE_EDITOR` and `KUBECTL_EXTERNAL_DIFF` out of the child environment, in upper and lower case. With isolation off, the child gets the environment as it is.

#### Scenario: The keys in the environment of the person
- **WHEN** the environment holds one of these keys, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

#### Scenario: Isolation off
- **WHEN** the environment holds `GH_BROWSER` and `KUBE_EDITOR`, and a caller builds a child environment with isolation off
- **THEN** the child environment holds both keys with their values

### Requirement: A gh or kubectl key that names a file or a value reaches the child
`build_subprocess_env` SHALL put `GH_CONFIG_DIR`, `KUBECONFIG`, `XDG_DATA_HOME`, `GH_TOKEN`, `GH_HOST`, `GH_REPO` and `GH_PROMPT_DISABLED` of the caller override in the child environment with their values, with isolation on and off. It SHALL do the same for a key that only contains a refused name.

#### Scenario: Configuration, kubeconfig, data directory and gh settings
- **WHEN** a caller builds a child environment with the overrides `GH_CONFIG_DIR`, `KUBECONFIG`, `XDG_DATA_HOME`, `GH_TOKEN`, `GH_HOST`, `GH_REPO`, `GH_PROMPT_DISABLED`, `EXAMPLE_GH_BROWSER` and `KUBECTL_EXTERNAL_DIFF_EXAMPLE`
- **THEN** the child environment holds each of these keys with its value

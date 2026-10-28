# subprocess-environment Specification

## Purpose
Which caller overrides of the environment of a child process devops-cli refuses, and what a refusal reports. Each refused key makes the dynamic loader, the shell or the interpreter of the child load or run code that the caller did not choose. An isolated child does not get a refused key from the environment.

## Requirements

### Requirement: A caller override that loads code into the child is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` when the upper-case form of a key of the caller override is `LD_AUDIT`, `LD_LIBRARY_PATH`, `LD_ORIGIN_PATH`, `LD_PRELOAD`, `GCONV_PATH`, `BASH_ENV`, `ENV`, `SHELLOPTS`, `BASHOPTS` or `PS4`, or starts with `DYLD_` or `BASH_FUNC_`. It SHALL do this with environment isolation on and off.

#### Scenario: A glibc audit library
- **WHEN** a caller builds a child environment with the override `LD_AUDIT` or `ld_audit`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A glibc gconv module path
- **WHEN** a caller builds a child environment with the override `GCONV_PATH` or `gconv_path`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A macOS loader key
- **WHEN** a caller builds a child environment with the override `DYLD_FRAMEWORK_PATH`, `DYLD_FALLBACK_LIBRARY_PATH`, `DYLD_FALLBACK_FRAMEWORK_PATH`, `DYLD_VERSIONED_LIBRARY_PATH`, `DYLD_IMAGE_SUFFIX` or `DYLD_EXAMPLE_KEY`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: An exported bash function
- **WHEN** a caller builds a child environment with the override `BASH_FUNC_x%%`, `bash_func_x%%`, `BASH_FUNC_x()` or `BASH_FUNC_git%%`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A bash option or trace prompt
- **WHEN** a caller builds a child environment with the override `SHELLOPTS`, `BASHOPTS` or `PS4`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A caller override outside the refused families reaches the child
`build_subprocess_env` SHALL put each other key of the caller override in the child environment with its value, also a key that contains a refused name but does not start with it.

#### Scenario: Usual keys and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `PATH`, `HOME`, `ENVIRONMENT`, `EXAMPLE_DYLD_FLAG` and `BASH_FUNCTIONS`
- **THEN** the child environment holds each of these keys with its value

### Requirement: The rule pack test gives Semgrep only its own setting
`run_rule_pack_tests` SHALL give `semgrep --version` and `semgrep --test` the override `SEMGREP_ENABLE_VERSION_CHECK=0` and no other key, so the child gets the isolated environment that `build_subprocess_env` builds.

#### Scenario: An exported bash function and a token in the environment of the person
- **WHEN** the environment holds `BASH_FUNC_which%%` and `GITHUB_TOKEN`, and `run_rule_pack_tests` runs on a copy of the rule pack
- **THEN** `semgrep --version` and `semgrep --test` each start with the caller override `{"SEMGREP_ENABLE_VERSION_CHECK": "0"}` and no other key

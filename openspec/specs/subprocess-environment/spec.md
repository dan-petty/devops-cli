# subprocess-environment Specification

## Purpose
Which caller overrides of the environment of a child process devops-cli refuses, and what a refusal reports. Each refused key makes the dynamic loader, the shell or the interpreter of the child load or run code that the caller did not choose. An isolated child does not get a refused key from the environment, unless the caller names the key in `extra_allowed_keys`.

## Requirements

### Requirement: A caller override that loads code into the child is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` when the upper-case form of a key of the caller override is a loader, gconv, shell or interpreter key that a scenario of this requirement names, or starts with `DYLD_` or `BASH_FUNC_`. It SHALL do this with environment isolation on and off.

#### Scenario: A glibc audit library
- **WHEN** a caller builds a child environment with the override `LD_AUDIT` or `ld_audit`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A glibc loader path or preload
- **WHEN** a caller builds a child environment with the override `LD_LIBRARY_PATH`, `LD_ORIGIN_PATH` or `LD_PRELOAD`, in upper or lower case
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

#### Scenario: A shell start-up file
- **WHEN** a caller builds a child environment with the override `BASH_ENV` or `ENV`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A bash option or trace prompt
- **WHEN** a caller builds a child environment with the override `SHELLOPTS`, `BASHOPTS` or `PS4`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A zsh start-up, function or null-command key
- **WHEN** a caller builds a child environment with the override `ZDOTDIR`, `FPATH`, `NULLCMD` or `READNULLCMD`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Python path or start-up key
- **WHEN** a caller builds a child environment with the override `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `PYTHONPLATLIBDIR` or `PYTHONPYCACHEPREFIX`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Node.js, Perl or Ruby key that loads code
- **WHEN** a caller builds a child environment with the override `NODE_OPTIONS`, `NODE_PATH`, `NODE_COMPILE_CACHE`, `NODE_REPL_EXTERNAL_MODULE`, `PERL5OPT`, `PERL5LIB`, `PERLLIB`, `PERL5DB`, `RUBYOPT` or `RUBYLIB`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Java option or class path
- **WHEN** a caller builds a child environment with the override `JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS`, `_JAVA_OPTIONS` or `CLASSPATH`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A caller override outside the refused families reaches the child
`build_subprocess_env` SHALL put each other key of the caller override in the child environment with its value: a key that contains a refused name but does not start with it, and an interpreter key that loads no code.

#### Scenario: Usual keys and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `PATH`, `HOME`, `ENVIRONMENT`, `EXAMPLE_DYLD_FLAG`, `BASH_FUNCTIONS`, `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE` and `NODE_ENV`
- **THEN** the child environment holds each of these keys with its value

### Requirement: The rule pack test gives Semgrep only its own setting
`run_rule_pack_tests` SHALL give `semgrep --version` and `semgrep --test` the override `SEMGREP_ENABLE_VERSION_CHECK=0` and no other key, so the child gets the isolated environment that `build_subprocess_env` builds.

#### Scenario: An exported bash function and a token in the environment of the person
- **WHEN** the environment holds `BASH_FUNC_which%%` and `GITHUB_TOKEN`, and `run_rule_pack_tests` runs on a copy of the rule pack
- **THEN** `semgrep --version` and `semgrep --test` each start with the caller override `{"SEMGREP_ENABLE_VERSION_CHECK": "0"}` and no other key

### Requirement: An isolated child gets no refused key from the environment
With environment isolation on, `build_subprocess_env` SHALL keep each key that the caller override refuses out of the child environment when the key is in the environment of the process and the caller names no `extra_allowed_keys`.

#### Scenario: Refused keys in the environment of the person
- **WHEN** the environment holds `PYTHONPATH`, `PYTHONHOME`, `ZDOTDIR`, `NODE_OPTIONS`, `PERL5LIB`, `LD_PRELOAD`, `BASH_ENV` and each other refused key, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

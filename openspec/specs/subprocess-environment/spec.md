# subprocess-environment Specification

## Purpose
Which caller overrides of the environment of a child process devops-cli refuses, and what a refusal reports. Each refused key makes the dynamic loader, the shell, the interpreter, git, ssh or a library load or run code that the caller did not choose. An isolated child does not get a refused key from the environment, unless the caller names the key in `extra_allowed_keys`.

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

### Requirement: A caller override of a git key that devops-cli does not set is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `GIT_`, but not for the five keys of the next requirement. It SHALL refuse `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE` and `MERGE_TOOLS_DIR` in the same way. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: A git configuration key
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_12`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_GLOBAL` or `GIT_CONFIG_SYSTEM`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A program that git starts
- **WHEN** a caller builds a child environment with the override `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_PAGER`, `GIT_EXTERNAL_DIFF` or `GIT_PROXY_COMMAND`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A directory of git programs or hooks, and the ext transport
- **WHEN** a caller builds a child environment with the override `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR` or `GIT_ALLOW_PROTOCOL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A key that the source or a script of git reads
- **WHEN** a caller builds a child environment with the override `GIT_TEST_FSMONITOR`, `GIT_TEST_MAINT_SCHEDULER`, `GIT_DIFFTOOL_EXTCMD` or `MERGE_TOOLS_DIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A trace key that writes a file
- **WHEN** a caller builds a child environment with the override `GIT_TRACE`, `GIT_TRACE2` or `GIT_TRACE_CURL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A git key that no caller sets
- **WHEN** a caller builds a child environment with the override `GIT_SSH_VARIANT`, `GIT_CONFIG_NOSYSTEM` or `GIT_EXAMPLE_KEY`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The editor, the pager and their filters
- **WHEN** a caller builds a child environment with the override `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN` or `LESSCLOSE`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A git key that devops-cli sets reaches the child
`build_subprocess_env` SHALL put `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` of the caller override in the child environment with their values. It SHALL do the same for a key that only contains a refused git name, and for `XDG_CONFIG_HOME`.

#### Scenario: The five git keys and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GITHUB_STEP_SUMMARY`, `EXAMPLE_GIT_SSH_COMMAND` and `XDG_CONFIG_HOME`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: The ambient allowlist holds no refused key
No key of `DEFAULT_ALLOWED_ENV_VARS` SHALL be a key that `build_subprocess_env` refuses from a caller.

#### Scenario: Each allowed key as an override
- **WHEN** a caller builds a child environment with one key of `DEFAULT_ALLOWED_ENV_VARS` as the override
- **THEN** `build_subprocess_env` raises no error, and the child environment holds the key with its value

### Requirement: The fetch of an Argo CD revision never asks a question
`render_at_revision` SHALL run `git fetch` with the argument `-c` and the value `core.sshCommand=ssh -o BatchMode=yes`. It SHALL give each command the environment override `GIT_TERMINAL_PROMPT=0` and no other git key. The override passes the guard, so the fetch of an SSH remote starts `ssh` with `-o BatchMode=yes`.

#### Scenario: A fetch over SSH through run_subprocess
- **WHEN** `render_at_revision` fetches the SSH remote `ssh://git@example.com/repository.git` through `run_subprocess`, and a stand-in `ssh` program is first on `PATH`
- **THEN** the stand-in `ssh` starts with the arguments `-o BatchMode=yes`
- **AND** no `SecurityError` is raised before the fetch fails

### Requirement: A git command that writes the global configuration uses the file that the environment names
The calls `git config --global` of `devops ssh register`, `devops ssh rotate` and `devops devcontainer post-start` SHALL name `GIT_CONFIG_GLOBAL` in `extra_allowed_env`. When the environment holds the key, each call writes in the file that the key names, as `git config --global` does in a shell.

#### Scenario: The signing key of a registered SSH key
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops ssh register` runs
- **THEN** that file holds `gpg.format`, `user.signingkey` and `commit.gpgsign`

#### Scenario: The git defaults of the post-start step
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops devcontainer post-start` runs
- **THEN** that file holds `push.autoSetupRemote` set to `true` and `init.defaultBranch` set to `main`
- **AND** the home directory holds no `.gitconfig`

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

### Requirement: A caller override of a key that makes a library or Python load a module is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `OPENSSL` or `KRB5`. It SHALL do the same for `GSS_MECH_CONFIG`, `SASL_PATH`, `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__`. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: An OpenSSL configuration file, provider directory or engine directory
- **WHEN** a caller builds a child environment with the override `OPENSSL_CONF`, `OPENSSL_CONF_INCLUDE`, `OPENSSL_MODULES` or `OPENSSL_ENGINES`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: An OpenSSL key that loads no module
- **WHEN** a caller builds a child environment with the override `OPENSSL_SEC_MEM`, `OPENSSL_ia32cap`, `OPENSSL_EXAMPLE_KEY` or `OPENSSL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Kerberos key
- **WHEN** a caller builds a child environment with the override `KRB5_CONFIG`, `KRB5_KTNAME`, `KRB5_KDC_PROFILE`, `KRB5_TRACE`, `KRB5CCNAME`, `KRB5_CLIENT_KTNAME` or `KRB5RCACHEDIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The GSS-API mechanism file and the SASL plug-in directory
- **WHEN** a caller builds a child environment with the override `GSS_MECH_CONFIG` or `SASL_PATH`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Python launcher key
- **WHEN** a caller builds a child environment with the override `PYTHONEXECUTABLE` or `__PYVENV_LAUNCHER__`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A caller override outside the refused keys reaches the child
`build_subprocess_env` SHALL put each key of the caller override that no refused key or family matches in the child environment with its value. A key matches a family only when it starts with `OPENSSL` or `KRB5`. A key matches another refused key only when it is that key.

#### Scenario: Keys that load no module
- **WHEN** a caller builds a child environment with the overrides `SSL_CERT_FILE`, `SSL_CERT_DIR`, `CURL_CA_BUNDLE`, `CURL_HOME`, `NODE_EXTRA_CA_CERTS`, `LOCPATH`, `NLSPATH`, `GNUTLS_DEBUG_LEVEL`, `P11_KIT_DEBUG`, `SASL_CONF_PATH` and `LDAPCONF`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

#### Scenario: Keys that only look like a refused key
- **WHEN** a caller builds a child environment with the overrides `EXAMPLE_OPENSSL_CONF`, `EXAMPLE_KRB5_CONFIG`, `GSS_MECH_CONFIGURATION`, `SASL_PATHS` and `PYTHONEXECUTABLES`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: An isolated child gets no library key from the environment
With environment isolation on, `build_subprocess_env` SHALL keep each key that the first requirement refuses out of the child environment. This holds when the key is in the environment of the process and the caller names no `extra_allowed_keys`.

#### Scenario: Library keys in the environment of the person
- **WHEN** the environment holds `OPENSSL_CONF`, `KRB5_CONFIG`, `GSS_MECH_CONFIG`, `SASL_PATH` and `__PYVENV_LAUNCHER__`, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

### Requirement: A refused library key starts no child
`run_subprocess` SHALL raise `SecurityError` for a refused key in its `env` argument before it starts the program.

#### Scenario: An OpenSSL configuration in the environment of a program
- **WHEN** a caller runs a program through `run_subprocess` with the override `OPENSSL_CONF`
- **THEN** `run_subprocess` raises `SecurityError`
- **AND** the program does not start

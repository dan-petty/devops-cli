# Proposal

## Why

Issue #2503: the subprocess environment guard accepts the library keys that make a child load a module from a place that the caller chooses.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. The patterns hold the loader, gconv, bash, zsh, interpreter and git keys (#2205, #2433, #2429, #2483). They hold no library key.
- `OPENSSL_CONF` names an OpenSSL configuration file that can name a provider or an engine, which is a shared library. `OPENSSL_CONF_INCLUDE`, `OPENSSL_MODULES` and `OPENSSL_ENGINES` name the directory of included files, of providers and of engines. `openssl-env(7)` calls these four keys security-sensitive.
- Each program that links OpenSSL reads these keys, for example `openssl`, `curl`, `ssh`, `node` and the `ssl` module of Python. A Kerberos configuration file can name plug-in modules in the same way.
- The design of #2429 and of #2483 record these keys as a non-goal for #2503. The issue asks for the libraries that devops-cli children use, and for the keys of each library that load a module.
- The inventory found more keys than the issue names: `GSS_MECH_CONFIG`, `SASL_PATH`, and two keys of Python that pick a virtual environment, `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__`.

## What Changes

- The guard refuses these keys of a caller, in a block of its own in `CONST_CODE_LOADING_ENV_PATTERNS`: each `OPENSSL` key, each `KRB5` key, `GSS_MECH_CONFIG`, `SASL_PATH`, `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__`. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- The two families are patterns (`OPENSSL*` and `KRB5*`), not lists of names. No caller sets a key of them, so the change needs no list of accepted keys. The design says why.
- No key of `DEFAULT_ALLOWED_ENV_VARS` or of `DEFAULT_ALLOWED_ENV_PREFIXES` matches a new pattern. Thus an isolated child gets none of the new keys from the environment, and the change edits no allowlist.
- The design names each key that the change checked and left accepted, with the reason. `SSL_CERT_FILE` and `SSL_CERT_DIR` are two of them.
- `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec name the library keys as refused keys. Both said that the library keys stay accepted (#2503).
- The refusal is what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the keys that make a library or Python load a module, a plug-in or a virtual environment of the caller. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py`.
- Tests: `tests/test_subprocess_env_boundary.py`.
- Documents: `ARCHITECTURE.md`, and the purpose of `openspec/specs/subprocess-environment/spec.md`.

## Feasibility

The premise is true on `origin/main` at `5bb1ed0f`, and the item can be built as written. The probes ran in a temporary directory, with `env -i`, a temporary `HOME` and fake values. A shared object with a constructor wrote a marker. A version of each program is in the list at the end of this section.

- The guard accepts the keys today. The command of step 1 of the issue printed the keys `OPENSSL_CONF`, `OPENSSL_MODULES` and `OPENSSL_ENGINES`, and `KRB5_CONFIG`, with no `SecurityError`. `DEFAULT_ALLOWED_ENV_VARS` and `DEFAULT_ALLOWED_ENV_PREFIXES` hold no key of these families.
- `OPENSSL_CONF` with a provider section (the files of step 3 of the issue) ran the module in `node -e 0`, `curl --version`, `python3 -c 'import ssl; ...'`, `python3 -c 'import hashlib; ...'`, `openssl version` and `ssh -V`. `git ls-remote ssh://...` ran it in the `ssh` child. `git ls-remote https://...` did not run it: git of this container links `libcurl-gnutls`, not OpenSSL. Thus the claim of the issue holds for git over SSH, and for a git build that links OpenSSL.
- `OPENSSL_MODULES` made `openssl list -providers -provider legacy` load `legacy.so` from the directory of the key. A configuration that names a provider (`legacy = legacy_section`) made `openssl version` load the same file from that directory. The key alone with the stock configuration loads nothing, because the stock configuration names no provider.
- `OPENSSL_CONF_INCLUDE` made `openssl version` read the file `inc.cnf` from the directory of the key, for a configuration with the line `.include inc.cnf`. That file named the provider module, and the module ran. The key alone with the stock configuration loads nothing, because the stock `/etc/ssl/openssl.cnf` includes no relative file.
- `OPENSSL_ENGINES` made `openssl engine -t p` load `p.so` from the directory of the key. The page `openssl-env(7)` says that these four keys are security-sensitive.
- `KRB5_CONFIG`, with a `[plugins]` section that has `hostrealm = { module = m:<dir>/q.so }`, made `krb5_get_host_realm` of `libkrb5` load the module. The page `krb5.conf(5)` of MIT Kerberos defines `modulename:pathname`. `curl --negotiate` did not load it in this container, because it stopped at `gss_acquire_cred` with no credentials. The default `env_delete` table of sudo removes `KRB5_CONFIG*` and `KRB5_KTNAME`.
- `GSS_MECH_CONFIG` made `curl --negotiate -u :` and `git-remote-http` load the library that the file of the key lists for an unknown mechanism, when the server asks for `WWW-Authenticate: Negotiate`. The page `kerberos(7)` says the key names the file with the GSS-API mechanism module configuration. `ssh` of this container has no GSSAPI option.
- `SASL_PATH` made `sasl_client_init` of `libsasl2` load the plug-in from the directory of the key. `libcurl` and `git-remote-http` link `libsasl2` through `libldap`, but no child here calls `sasl_client_init` without an LDAP server, so this probe is at library level. `SASL_CONF_PATH` loaded nothing in the same probe.
- `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__` made `/usr/bin/python3 -c pass` and the `python` of the project virtual environment run the `.pth` line of a virtual environment that the key names. `Modules/getpath.py` of CPython reads both keys with no check of the platform. The Python documentation of the environment variables says that `PYTHONEXECUTABLE` works on macOS only, but the probe ran on Linux. #2429 did not refuse either key.
- The inventory ran every child with a preloaded library that logs each `getenv` name: `git` (status, HTTPS, SSH), `ssh`, `curl` (HTTPS, negotiate, LDAP, SMTP), `python3`, the project `python`, `semgrep`, `bandit`, `node`, `gpg`, `openssl`, `perl`, `bash` and `zsh`. `kubectl`, `helm`, `trivy`, `gh` and `docker` are static Go binaries that the preload does not reach. The strings of each linked library gave the keys of libraries that are lazy.
- No caller sets a key of the new patterns. A search of `src/`, `tests/`, `.github/`, `k8s/`, `docs/` and the container files finds the names only in `ARCHITECTURE.md`. The callers that pass an env override are `refine`, `samples`, `ssh_keys`, `devcontainer`, `semconv`, `canary`, `rules_pack`, `install_tools`, `cluster_runtime`, `image_pins`, `tunnel`, `argocd_overrides`, `dive`, `golangci_lint`, `tool_executor`, `mypy`, `cosign` and the `ci` command. None of them builds a key that the patterns match.
- The program versions are: OpenSSL 3.6.5 (`openssl`, `curl 8.23.0`), OpenSSH 10.6p1, git 2.55.0, Node.js v24.22.1, Python 3.14.9 and 3.14.10, MIT Kerberos 1.22.1, Cyrus SASL 2.1.28, GnuTLS 3.8.13, p11-kit 0.26.5 and semgrep-core 1.178.0.

## Existing Tool Considered

The default `env_delete` table of sudo (`initial_badenv_table` in `plugins/sudoers/env.c`) is the maintained, open list of keys that change the code that a program runs. It names `KRB5_CONFIG*` and `KRB5_KTNAME` (when sudo has Kerberos support) and `NLSPATH`. It names no OpenSSL key and none of the other keys of this change. `openssl-env(7)` is the OpenSSL project's own list of security-sensitive keys, and `kerberos(7)` lists the Kerberos keys. No library publishes a list for import, so the constant names the sources, as #2205, #2429 and #2483 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The change builds no new function, flag or step, and it deletes no code.

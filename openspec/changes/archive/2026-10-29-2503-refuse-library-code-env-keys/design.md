# Design

## Decisions

- **The sources are the manual pages, CPython and a probe.** `openssl-env(7)` is the OpenSSL project's list of security-sensitive keys. `kerberos(7)` and `krb5.conf(5)` of MIT Kerberos list the Kerberos keys and the plug-in syntax. `Modules/getpath.py` of CPython reads the launcher keys of Python. The default `env_delete` table of sudo names `KRB5_CONFIG*` and `KRB5_KTNAME`. A probe with the real program confirms each refused key (proposal, Feasibility).
- **The refused keys, with their sources.**

  | Family | Keys | Source and probe |
  | :--- | :--- | :--- |
  | OpenSSL | each `OPENSSL` key, among them `OPENSSL_CONF`, `OPENSSL_CONF_INCLUDE`, `OPENSSL_MODULES`, `OPENSSL_ENGINES` | `openssl-env(7)`; probes with `node`, `curl`, `ssh`, `openssl` and `python3` |
  | Kerberos | each `KRB5` key, among them `KRB5_CONFIG`, `KRB5_KTNAME`, `KRB5CCNAME` | `kerberos(7)`, `krb5.conf(5)`, sudo; probe with `libkrb5` |
  | GSS-API | `GSS_MECH_CONFIG` | `kerberos(7)`; probe with `curl --negotiate` and `git-remote-http` |
  | Cyrus SASL | `SASL_PATH` | `_sasl_get_default_path` in `lib/common.c` of Cyrus SASL; probe with `libsasl2` |
  | Python | `PYTHONEXECUTABLE`, `__PYVENV_LAUNCHER__` | `Modules/getpath.py` of CPython; probe with `python3` |

- **OpenSSL and Kerberos are families, not lists of names.** The constant holds the patterns `OPENSSL*` and `KRB5*`. A list of names stays incomplete when the library adds a key, which #2483 found for git and answered with a family. The refine of this item chose exact names, because it assumed that a caller has a reason to set such a key. A search of `src/`, `tests/`, `.github/`, `k8s/` and `docs/` finds no caller that sets one. A key that a library adds later stays refused until a person reviews it.
- **Keys of the families that load no module are refused too.** `OPENSSL_SEC_MEM`, `OPENSSL_ia32cap`, `OPENSSL_TRACE`, `KRB5_TRACE`, `KRB5CCNAME`, `KRB5_CLIENT_KTNAME`, `KRB5_KDC_PROFILE` and `KRB5RCACHEDIR` ride with their family. No caller needs one, and a refusal costs nothing. `OPENSSL` names the `openssl` program for the scripts `CA.pl` and `c_rehash` (`openssl-env(7)`). `KRB5_KTNAME` is in the table of sudo. A caller that needs one key later adds one exception, as `CONST_GIT_ACCEPTED_ENV` does for git. The change adds no exception list now, because it would be empty.
- **The other library keys are exact names.** `GSS_*` and `SASL_*` are not families that the libraries read. `libldap` names its `SASL_` options in `ldap.conf` and reads no key of that name. A pattern would refuse keys of other programs. `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__` are exact for the reason in the design of #2429: `PYTHONUNBUFFERED` and the other keys that load no code stay accepted.
- **The two Python keys differ from the rest.** They belong to the interpreter family of #2429, which did not name them. Python takes `sys.executable` from either key, then reads the `pyvenv.cfg` that sits next to it. The `home` line picks the standard library, and the `.pth` files of its `site-packages` run their `import` lines. The probe ran such a line in `/usr/bin/python3` and in the project `python`. The documentation of Python says `PYTHONEXECUTABLE` works on macOS only, but `getpath.py` has no check of the platform.
- **The block has a heading comment and one comment per family.** Each family has a short comment with its pages, for example `# openssl-env(7)`. The constant reads as one block for each group of keys: the loader and interpreter keys, the git keys and the library keys. A reader finds the source of each key next to it.
- **The comment of the constant keeps the length rule of #2433.** The comment above `CONST_CODE_LOADING_ENV_PATTERNS` stays at 25 words, and the change does not edit it.
- **No refused key reaches an isolated child from the environment, and the change edits no allowlist.** No key of `DEFAULT_ALLOWED_ENV_VARS` and no prefix of `DEFAULT_ALLOWED_ENV_PREFIXES` matches a new pattern. The existing test of the allowlist gives each allowed key as an override. A new test sets each refused key in the environment and checks that the isolated child holds none. This pins the issue's remark that the defect is the caller override only.
- **The tests are in the file of the behaviour, with a tuple of their own.** `REFUSED_LIBRARY_KEYS` sits beside `REFUSED_OVERRIDE_KEYS`, and two tests use it. The library keys have their own spec requirements, so they have their own tuple and tests. Two tests check the keys that reach the child. One test gives `run_subprocess` a refused key and checks that the program does not start.
- **The spec change only adds requirements.** The requirement "A caller override that loads code into the child is refused" names a closed list of keys. The library keys have requirements of their own, as the git keys have. A delta cannot change a purpose, so the change edits the purpose line of `openspec/specs/subprocess-environment/spec.md` directly, as #2429 and #2483 did.

## Rejected alternatives

- **Exact names for the five keys of the refine.** It leaves `GSS_MECH_CONFIG` and `SASL_PATH` open, and the probes show that each one loads a library. It leaves the Python launcher keys open. It also leaves `OPENSSL_SEC_MEM` and each key that OpenSSL adds later accepted, with no caller that needs one.
- **A deny-by-default list of accepted keys, as for git.** The list would be empty: no caller sets a key of the families. An empty list is code that nothing uses.
- **A pattern for the whole group `SSL_*`, `CURL_*` or `GNUTLS_*`.** It refuses `SSL_CERT_FILE`, which `tests/support/certificates.py` sets, and keys that load no code. The next section says why those stay accepted.
- **Start each child in a mode that ignores the key.** `OPENSSL_CONF` has no such mode, and the programs that read it are not all Python. The guard in `build_subprocess_env` covers every child in one place.

## Keys considered and accepted

| Key | Why it stays accepted | Evidence |
| :--- | :--- | :--- |
| `SSL_CERT_FILE`, `SSL_CERT_DIR`, `CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`, `CTLOG_FILE` | They name certificate or log data, which the library parses and does not load as code. They change which servers a child trusts, not which code it runs. | A probe gave the shared object of the marker as the file: `curl`, `python3` and `openssl` ran no code. |
| `HOME`, `XDG_CONFIG_HOME`, `CURL_HOME` | A caller must be able to give a child its own configuration directory (#2429, #2483). `p11-kit` loads the module that `$HOME/.config/pkcs11/modules/*.module` names, unless `P11_KIT_NO_USER_CONFIG=1`. `curl` reads `.curlrc`, but has no option that loads a module by a path: an `engine` line made `curl` exit with status 53 and run nothing. | A probe with `p11-kit list-modules` ran the marker with `HOME` and with `XDG_CONFIG_HOME`. A probe with a `.curlrc` ran nothing. `curl(1)` lists the keys. |
| `LOCPATH`, `NLSPATH` | glibc reads a locale or a message catalog from the directory as data. No code loads. sudo removes `NLSPATH` from the environment of a program that runs for another user, but the probe shows that no module loads. | A probe with the shared object as `LC_CTYPE` made `setlocale` fail and ran no code. `catopen` returned -1. |
| `GNUTLS_SYSTEM_PRIORITY_FILE`, `GNUTLS_DEBUG_LEVEL`, `GNUTLS_NO_EXPLICIT_INIT`, `GNUTLS_NO_IMPLICIT_INIT`, `GNUTLS_BUFFER_RECLAIM`, `GNUTLS_CPUID_OVERRIDE`, `GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID`, `P11_KIT_DEBUG`, `P11_KIT_STRICT`, `P11_KIT_URI_LOWERCASE` | The names in `libgnutls` and `libp11-kit` are these keys. None names a module, a directory of modules or a file with module names. | The strings of both libraries, and the `getenv` log of the `git` HTTPS child. |
| `LDAPCONF`, `LDAPRC`, `LDAPNOINIT` | No option of `ldap.conf(5)` names a library, a plug-in or a module directory. | `ldap.conf(5)` of OpenLDAP 2.6. |
| `SASL_CONF_PATH` | The client library reads no configuration file at `sasl_client_init`. `SASL_PATH`, the plug-in directory, is refused. | A probe with a plug-in in the directory of the key ran no code. |
| `OCAMLLIB`, `CAMLLIB` | `semgrep-core` is native OCaml code. It does not read `ld.conf` for stub libraries. | A probe with an `ld.conf` and a shared object ran no code in `semgrep` and `semgrep-core`. |
| `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE` and similar | They make a child write a file. They load no module. | A probe wrote TLS secrets to the file. #2674 holds the decision for this class. |
| `UV_PYTHON`, `npm_config_script_shell` and the Go keys | They name a program, not a module or a library. | A probe ran the program of each key. #2673 holds the decision for this class. |
| The keys of PAM and NSS | No child links `libpam` or `libnss3`, and the strings of `libpam` hold no key. `libnss3` is not in the devcontainer, so no probe could run. A child that links NSS needs its own review. | `ldd` of `ssh`, `curl`, `git` and `git-remote-http`. |

## Non-goals

- The keys of `ssh` that name a program, `SSH_ASKPASS` and `SSH_ASKPASS_REQUIRE`: #2633.
- The keys that make `uv`, `npm` or `go` start a program: #2673.
- The keys that make a child write a file that the caller names: #2674.

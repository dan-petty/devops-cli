# Design

## Decisions

- **The sources are the OpenSSH manuals and source.** The pages `ssh(1)`, `ssh-add(1)`, `ssh-keygen(1)` and `ssh-agent(1)` name five keys. The `getenv` calls of the OpenSSH source name two more: `SSH_SK_HELPER` and `SSH_PKCS11_HELPER`. A probe with OpenSSH 10.6p1 and a temporary `HOME` confirms each key that the guard refuses (proposal, Feasibility).
- **An `SSH_` key is refused.** The constant holds the pattern `SSH_*`. The git change (#2483) found a list of names incomplete, because two helper keys are in no page. The same holds here, and OpenSSH adds keys with each release.
- **The guard keeps no accepted set for `SSH_` keys.** #2483 needed `CONST_GIT_ACCEPTED_ENV` because five callers set a git key. No file of `src/` or `tests/` sets an `SSH_` key as a caller override, so an accepted set would be dead code. A caller that needs one adds the set in the review that the new key needs.
- **`SSH_AUTH_SOCK` is refused.** A caller that names the socket chooses the agent. `ssh-add` gives the private key to that agent, and `ssh` asks it to sign. The `*AUTH*` pattern of `DEFAULT_DENIED_ENV_PATTERNS` already keeps the key out of an isolated child, so no ambient use is lost. With `isolate_env=False` the key of the person reaches the child as before.
- **`SHELL` is refused, and the allowlist drops it.** `ssh` starts the program of `SHELL` to run a `ProxyCommand`, a `LocalCommand` and a `Match exec` test. A `ProxyJump` becomes a `ProxyCommand`, so a configuration with a jump host is enough. The guard must refuse the key, and a key of the allowlist is never a refused key (the requirement of #2483). The shell of a child is then the system shell: `ssh` uses `/bin/sh` when `SHELL` is not set. #2429 and #2483 removed `PYTHONPATH`, `PYTHONHOME`, `EDITOR` and `PAGER` on the same ground. A person who wants the ambient value uses `isolate_env=False` or the `extra_allowed_env` of a caller. No file of `src/` or `tests/` reads or sets `SHELL` for a child.
- **The constant keeps the length rule of #2433.** The comment above `CONST_CODE_LOADING_ENV_PATTERNS` is not edited. The ssh block has one short comment for each pattern. The block sits between the git keys and the Python keys. A later change that appends a group at the end of the tuple (#2503) then merges with no conflict.
- **The spec change only adds requirements.** The requirement "A caller override that loads code into the child is refused" names the loader and interpreter keys, and #2503 changes it. The new requirements add the ssh refusal, the keys that stay accepted and the isolated child. A delta cannot change a purpose, so the change edits the purpose line of `openspec/specs/subprocess-environment/spec.md` directly, as #2429 and #2483 did.
- **The tests are in the file of the behavior.** `tests/test_subprocess_env_boundary.py` takes the refused keys in `REFUSED_OVERRIDE_KEYS`. The tests of the override, of the case and of the ambient environment then cover them. The test of the allowlist fails for a key that a refused pattern matches.

## Rejected alternatives

- **Refuse the ten keys by name.** The first idea. It misses `SSH_SK_HELPER` and `SSH_PKCS11_HELPER` if the author reads only the pages, and it misses the next key that OpenSSH adds.
- **Add `CONST_SSH_ACCEPTED_ENV` with `SSH_AUTH_SOCK`.** The issue guessed that the socket is "probably ambient and needed". The probe shows that a caller socket gets the private key of `ssh-add`. The key is not ambient for an isolated child. No caller needs it.
- **Keep `SHELL` in the allowlist and leave it accepted.** A caller could then run any program in a child `ssh` that reads a `ProxyJump`. The only reason to keep it is that nothing was found to need it.
- **Refuse `SHELL` as an override only, and keep it in the allowlist.** A refused key would then reach an isolated child from the environment. The requirement and its test forbid that.
- **Check the value of `SSH_ASKPASS`.** The value is a path, and a new option or another program name passes such a check.

## Keys considered and accepted

- `HOME`: `ssh` reads its configuration, its known hosts and its keys from the home directory of the account, not from `HOME`. A probe with a `ProxyCommand` in `$HOME/.ssh/config` changed nothing. `HOME` stays accepted, for the reason in #2483.
- `DISPLAY` and `WAYLAND_DISPLAY`: they let `ssh` use an askpass program, but they name none. With `SSH_ASKPASS` refused, the program is the compile-time default `/usr/bin/ssh-askpass`. Every X11 client trusts the display, and `devops devcontainer` gives them to a child on purpose.
- `XAUTHORITY`: `xauth` reads a cookie file from it. The file holds data, not code.
- `TMPDIR`: `ssh` makes its temporary directories below it. It names a place for files, not a program.
- `PATH`: `ssh` finds `xauth` and the program of a `ProxyCommand` with it. Each child needs `PATH`, so the guard accepts it for every program.
- `TERM`, `LANG` and `LC_*`: `ssh` sends them to the server, and the locale code reads them. They run nothing.
- `LISTEN_PID`, `LISTEN_FDS` and `NOTIFY_SOCKET`: only `ssh-agent` reads them, when systemd starts it. devops-cli never starts an agent, and the keys name no program.
- `KRB5CCNAME`, `AUTHSTATE`, `XDG_RUNTIME_DIR` and `TZ`: only `sshd` reads them. devops-cli never starts `sshd`.
- `${VAR}` in a configuration value: the person writes the name in the configuration. The key is not special.
- `SSHPASS` and any other key that starts with `SSH` and has no underscore after it: the pattern is `SSH_*`. The key of the `sshpass` tool is not an OpenSSH key.
- `COMSPEC`: it is the Windows counterpart of `SHELL`. No probe on Windows was possible, and devops-cli CI runs on Linux and macOS only.

## Non-goals

- The library keys that make a library of the child load a module, for example `OPENSSL_CONF` and `KRB5_CONFIG` (`ssh` links GSSAPI): #2503.
- The keys of `gh` and `kubectl` that name a program or a file with a program, for example `GH_BROWSER`, `GH_CONFIG_DIR` and `KUBECONFIG`: #2672. The probes of that issue ran a program with each of the three keys. Some of these keys name a file that callers set on purpose, so that issue needs its own design.

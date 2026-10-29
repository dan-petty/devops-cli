# Proposal

## Why

Issue #2633: the subprocess environment guard accepts the ssh keys that make an ssh child run a program that its caller did not choose.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. The patterns hold the loader, gconv, bash, zsh, interpreter and git keys (#2205, #2429, #2483). They hold no `SSH_` key.
- `SSH_ASKPASS` names the program that `ssh`, `ssh-add` and `ssh-keygen` start to ask for a passphrase. `SSH_ASKPASS_REQUIRE=force` makes them start it with a terminal present. Git also starts the program of `SSH_ASKPASS` when it needs a password.
- The probes found more keys of the same kind. `SSH_SK_PROVIDER` makes `ssh-keygen` and `ssh-add` load a library. `SSH_SK_HELPER` and `SSH_PKCS11_HELPER` name a helper program. `SHELL` names the program that `ssh` starts to run a `ProxyCommand`.
- `SSH_AUTH_SOCK` names the agent that gets the private key from `ssh-add`. `SSH_AGENT_PID` names the process that `ssh-agent -k` ends.
- `SHELL` is in `DEFAULT_ALLOWED_ENV_VARS`. A key of the allowlist must not be a refused key, so the guard cannot refuse `SHELL` while the allowlist holds it.

## What Changes

- The guard refuses each `SSH_` key and `SHELL` as a caller override. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- No `SSH_` key has an exception. No caller sets one, and the design says why the guard keeps no accepted set for them.
- `DEFAULT_ALLOWED_ENV_VARS` removes `SHELL`. Thus no refused key reaches an isolated child from the environment.
- `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec name the `SSH_` keys and `SHELL` as refused keys.
- The refusal and the isolated environment are what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the `SSH_` keys and `SHELL`, and an isolated child gets none of them from the environment. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py` and `src/devops_cli/core/process.py`.
- Tests: `tests/test_subprocess_env_boundary.py`.
- Documents: `ARCHITECTURE.md`, and the purpose of `openspec/specs/subprocess-environment/spec.md`.

## Feasibility

- The guard accepts the keys today. On `origin/main` at `ca9c1ad7`, step 1 of the issue printed `['SSH_ASKPASS', 'SSH_ASKPASS_REQUIRE']` with no `SecurityError`. Step 3, with OpenSSH 10.6p1, printed `SSH-ASKPASS-RAN`.
- Each probe below ran in a temporary directory. It used `env -i PATH=/usr/bin:/bin HOME=<dir>`, a fake value and a marker. The marker is a program or a library that prints a line. Each marker printed, so the program ran or the library loaded.
  - `ssh-keygen -y -f <key> </dev/null` ran the program of `SSH_ASKPASS` with `SSH_ASKPASS_REQUIRE=force`. It ran it with `DISPLAY` set and no `SSH_ASKPASS_REQUIRE`. It did not run it with neither.
  - `ssh` ran the program of `SSH_ASKPASS` for the host key question, with `StrictHostKeyChecking=ask`. The server was a throwaway SSH server on the loopback address. `git fetch` over SSH ran it too.
  - `git credential fill` ran the program of `SSH_ASKPASS` with git 2.55.0. Thus a git child with no SSH remote also runs it.
  - `SSH_SK_HELPER` ran with `ssh-keygen -K` and with `ssh-keygen -t ed25519-sk`.
  - `SSH_SK_PROVIDER` made `ssh-keygen -K` and `ssh-add -K` load a library. OpenSSH loads only a library that holds the symbol `sk_api_version`, and the constructor of the test library printed.
  - `SSH_PKCS11_HELPER` in the environment of `ssh-agent` ran when `ssh-add -s` added a PKCS#11 library. The log of `ssh-agent -d` shows `starting <program> -vvv`.
  - `SSH_AUTH_SOCK` made `ssh-add` give a private key to a second agent. `ssh-add -l` on that agent then listed the key. `SSH_AGENT_PID` made `ssh-agent -k` end a `sleep` process.
  - `SHELL` ran the program as the shell of a `ProxyCommand`. It ran for `ssh -o ProxyCommand=...`, for `ssh -o ProxyJump=...` and for a `ProxyCommand` in a file given with `ssh -F`. It ran for a `Match exec` line too. It did not run without one of these.
  - `SSH_CONNECTION`, `SSH_ORIGINAL_COMMAND`, `SSH_TTY`, `SSH_TUNNEL`, `SSH_USER_AUTH`, `SSH_CLIENT`, `SSH_ASKPASS_PROMPT` and `SSH_USE_STRONG_RNG` ran nothing with `ssh -G`, `ssh-keygen -y` and `ssh-add -l`.
  - `HOME` with a `ProxyCommand` in `$HOME/.ssh/config` changed nothing: `ssh -G` showed no proxy command. `ssh` reads its configuration from the home directory of the account.
- The `getenv` calls of the OpenSSH source on branch `master` name the keys. The files are `readpass.c`, `ssh-sk-client.c`, `ssh-pkcs11-client.c`, `ssh-agent.c`, `ssh-add.c`, `ssh-keygen.c`, `authfd.c`, `sshconnect.c` and `readconf.c`. The `strings` of the installed `ssh`, `ssh-add`, `ssh-agent` and `ssh-keygen` programs show the same `SSH_` names.
- The pages `ssh(1)`, `ssh-add(1)`, `ssh-keygen(1)` and `ssh-agent(1)` list `SSH_ASKPASS`, `SSH_ASKPASS_REQUIRE`, `SSH_AUTH_SOCK`, `SSH_SK_PROVIDER` and `SSH_AGENT_PID`. No page lists `SSH_SK_HELPER` or `SSH_PKCS11_HELPER`. A list of names stays incomplete when OpenSSH adds a key.
- The callers: no file of `src/` or `tests/` gives an `SSH_` key or `SHELL` as a caller override. `src/devops_cli/sandbox/engine.py` reads `SSH_AUTH_SOCK` from `os.environ` to guard a mount. That read is not a caller override.
- The pattern `*AUTH*` of `DEFAULT_DENIED_ENV_PATTERNS` already keeps `SSH_AUTH_SOCK` out of an isolated child. No file of `src/` reads `SHELL` for a child, and `git log -S` gives no reason for it in the allowlist.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It lists no OpenSSH key. No library publishes a list for import, so the constant names the sources, as #2205, #2429 and #2483 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The change builds no new code path: it adds two patterns and deletes one key from the ambient allowlist.

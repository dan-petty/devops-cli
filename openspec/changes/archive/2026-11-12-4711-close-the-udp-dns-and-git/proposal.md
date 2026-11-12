# Proposal: Close the UDP, DNS and git gaps of the network floor

## Why

Closes #4711. The network block of the test floor patches only `connect`, `connect_ex`, `bind`, `listen` and `getaddrinfo` of `socket`. A UDP datagram that `sendto` or `sendmsg` sends, a lookup through `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr` or `getnameinfo`, and a real git child with an https or ssh remote all get out of a test. `docs/TESTING.md` says that the floor blocks all network and DNS access.

## What Changes

- `tests/conftest.py`: the network block also guards `socket.socket.sendto` and `socket.socket.sendmsg`. A datagram from an IPv4 or IPv6 socket to a host that is not loopback raises `RuntimeError` and fails the test, also when the code catches the error. A datagram to loopback passes, so a test can keep a loopback UDP server.
- `tests/conftest.py`: the block also guards `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr` and `getnameinfo`. A lookup that needs a DNS query raises the error of a name that the lookup does not find (`gaierror`, or `herror` for `gethostbyaddr`) and fails the test. A numeric or loopback host passes. A reverse lookup passes only for loopback or with `NI_NUMERICHOST`.
- `tests/support/bootstrap.py`: the `.gitconfig` of the isolated HOME sets `protocol.allow = never` and `protocol.file.allow = user`. A real git child refuses each transport but the local one before it makes a lookup or starts a credential helper. The local transport keeps the default policy of git.
- `docs/TESTING.md`: the floor and "Exists today" lists name the new guards and the git config.
- No spec delta (`skip_specs: true`): the change alters only the test floor and its document. No command, option, message or service behavior changes.

This change fits one pull request.

## Capabilities

None.

## Impact

- Tests only. A test that sends a datagram to an external host, or that looks up an external name with these calls, now fails with `network edge reached without a fake`. The full suite passes with the change.
- A test that sets its own HOME does not get the git config of the floor. 14 test files set HOME (`grep -rln 'setenv("HOME"' tests`). A git child of such a test keeps the default transports of git, as before this change.

## Feasibility

- New tests run on `origin/main` 21b116eac: the six inner probes (`sendto`, `sendmsg`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr`, `getnameinfo`), each caught by `except Exception`, gave 6 passed and 0 errors. `git ls-remote https://example.com/example/repo.git` gave `fatal: repository 'https://example.com/example/repo.git/' not found`, so git reached the remote.
- `build_subprocess_env` (`src/devops_cli/core/process.py`) passes `HOME` (`DEFAULT_ALLOWED_ENV_VARS`) and removes each `GIT_*` key that `CONST_GIT_ACCEPTED_ENV` does not name, so `GIT_ALLOW_PROTOCOL` does not get to a git child, but a config file under HOME does.
- git 2.55.0, git-config(1) `protocol.allow`: when it is set, a transport with no `protocol.<name>.allow` takes its value. A local probe with `GIT_CONFIG_GLOBAL=/dev/null`: `-c protocol.allow=never` alone refuses a local clone (`transport 'file' not allowed`); with `-c protocol.file.allow=user` the clone passes, and with `GIT_PROTOCOL_FROM_USER=0` it is refused, which is the default policy of git for the file transport.
- Count of the set: `grep -rn "getfqdn|gethostbyname|gethostbyaddr|getnameinfo|.sendto(|sendmsg(|SOCK_DGRAM" src tests` finds no caller in `src/` or `tests/`. The guards stop calls from libraries.

## Existing Tool Considered

- git's own `protocol.allow` and `protocol.<name>.allow` settings cover the git part. The change writes them into the config file of the isolated HOME.
- pytest-socket blocks the creation of a socket with an error that the code under test can catch. The floor records each reach and fails the test also when the code catches the error, so the change extends the floor and deletes no code. Cost: about 20,000 tokens and 1 hour to build; the guards are about 100 lines in `tests/conftest.py` beside the existing ones.

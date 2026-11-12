# Design

## Decisions

- The send guard checks only IPv4 and IPv6 sockets. An `AF_NETLINK` or `AF_PACKET` socket also takes a tuple address, which is no host.
- A datagram to a loopback host passes, also to a port that no socket of the test binds. UDP has no refusal that a client sees, so the floor cannot refuse it as it refuses a loopback connect. The issue lists a loopback UDP server as an allowed case.
- Each refused lookup raises the error class of a name that the lookup does not find: `socket.gaierror` for `gethostbyname`, `gethostbyname_ex` and `getnameinfo`, `socket.herror` for `gethostbyaddr`. Code that handles a lookup failure takes the same path as in production, and the record of the floor fails the test.
- `gethostbyaddr` and `getnameinfo` pass only a loopback address, or `NI_NUMERICHOST`. The reverse lookup of a numeric address is a DNS query.
- `protocol.file.allow = user` keeps the default of git for the local transport. A plain local path or `file://` remote works, and a submodule clone of a local path is refused as in production.
- The send and lookup guards install from their own functions, `_install_send_guards` and `_install_lookup_guards`, which keeps `_install_network_guard` under the complexity limit of Ruff with no suppression.

## Rejected alternatives

- `GIT_ALLOW_PROTOCOL` in the environment of the test process: `build_subprocess_env` removes each `GIT_*` key that it does not accept, so the setting does not get to a git child that devops-cli starts.
- `protocol.file.allow = always`, as the audit plan wrote: it allows a submodule clone of a local path, which stock git refuses since 2.38.1. The tests then pass a path that production refuses.
- pytest-socket: it refuses the creation of a socket with an error that code can catch, and it records nothing, so a caught refusal passes the test.
- A check of the git argv in the process guard for a URL: it is a hand-made parser of git remotes, and it does not see a remote that the config of a repository names.

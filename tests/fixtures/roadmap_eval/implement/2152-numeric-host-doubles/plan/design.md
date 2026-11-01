# Design

## Decisions

- **Read in two steps: `ipaddress.ip_address(host)`, then `socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)`.** The first step reads every IPv4 and IPv6 literal, a zone ID included, with no help from the host. The second step reads the legacy IPv4 spellings with the rules of the C library. Evidence: `fe80::1%nope` makes `getaddrinfo` raise `gaierror`, because the zone needs an interface, so `getaddrinfo` cannot be the first step.
- **Take the first answer, `answers[0][4][0]`, and give it to `ipaddress.ip_address`.** A numeric host has one answer.
- **Catch `(OSError, UnicodeError)` and return `None`.** A host label longer than 63 characters or a long non-ASCII label makes `getaddrinfo` raise `UnicodeEncodeError`, which is a `ValueError` and no `OSError`. `vet_addresses` in `src/devops_cli/http/egress.py` catches the same pair. The callers of `parse_numeric_ip` have no `try`, so an uncaught error would crash an egress check.
- **Call `socket.getaddrinfo` directly.** The DNS seam of #1314 is open. When it lands, this call moves to it.
- **Accept the change in the edge spellings.** The new reader returns `None` for `0b11.1`, `0o17.1`, `+1.2.3.4`, `1_0.0.0.1`, `٣.0.0.1` and `127.0.0.1 ` with a trailing space. Only Python reads these as numbers, and a resolver reads them as names. The new reader returns `127.0.0.1` for `127。0。0。1`, as a resolver does. `is_loopback_or_private_host` refuses all of these hosts before and after, so no refusal is lost. `is_loopback_host` changes for `127。0。0。1` (now loopback) and `١٢٧.١` (no longer loopback). Each change matches what the resolver dials. A test in group 3 fixes the new results.
- **Make the test doubles pass a call with `AI_NUMERICHOST` before the code changes.** `ScriptedResolver` in `tests/web_fakes.py` answers for a name in its script and counts it, whatever the flags. With `AI_NUMERICHOST` set, a real resolver reads no name and counts nothing. The doubles in `tests/security/test_reference_address_classes.py` and `tests/security/test_reference_extraction.py` raise on every call. Both must pass a flagged call, and still fail on a call without the flag. This keeps the requirements of `sandbox-egress` ("resolves each name one time", "the whitelist validators resolve no name") true and tested.
- **Delete the dead branches with the three functions.** Nothing else holds them.
- **Write no spec delta.** No consumer-visible behavior changes for any spelling that a resolver reads.

## Rejected alternatives

- **`socket.inet_aton`.** TID251 bans it (`pyproject.toml:166-170`, #1107). `tests/commands/test_net_construct_rules.py` and `tests/invariants/test_architectural_invariants.py` fail if the ban goes.
- **Keep the hand-written parser and add the missing tests.** AGENTS.md rule 3 and #1107 make a hand-rolled address parser a defect. The parser also reads ten spellings differently from a resolver.
- **Use `getaddrinfo` alone.** `fe80::1%nope` fails there, as the evidence above shows.
- **Add a `validate_url` check or a spec delta in `public-api-egress`.** `validate_url` was deleted by #2845, and that capability covers the clients of fixed public APIs, not the reading of a host.

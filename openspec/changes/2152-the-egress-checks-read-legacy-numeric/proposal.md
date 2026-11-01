# Proposal

## Why

#2152: The egress and address checks in `src/devops_cli/core/validation.py` read a legacy numeric host, such as `0177.0.0.1`, `127.1` or `2130706433`, with a parser that devops-cli wrote itself (`_parse_part`, `_combine_ipv4_parts`, `_parse_legacy_ipv4`). AGENTS.md and #1107 make a hand-rolled address parser a defect. Some of its forms and some classifier branches have no test, and two of its branches cannot run.

## What Changes

- Pin the forms with tests first. The tests pass on the base and prove the new reader keeps every form that a resolver reads: octal, three-part, hex and zone-ID forms, a value that does not parse, and a host that makes the C library raise `UnicodeError`.
- Let the test doubles that stub `socket.getaddrinfo` pass a call that carries `AI_NUMERICHOST`. Such a call parses a numeric host and makes no DNS query. Three existing tests fail without this change.
- Write a test for the behavior that changes (it fails on the base), then make `parse_numeric_ip` read a legacy host with `ipaddress.ip_address` and then `socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)`.
- Delete `_parse_part`, `_combine_ipv4_parts` and `_parse_legacy_ipv4`. This deletes the two branches that cannot run: the `return None` for more than four parts, and the `except OSError, ValueError` around a parser that raises neither.
- Not in this change: the repeated metadata check in `_enforce_non_private_ssrf`. Commit 6ebc9683 (#2845) deleted that function and `validate_url`, so nothing is left to delete.
- Not in this change: the DNS seam of #1314. It is open, so the call goes to `socket.getaddrinfo` directly.
- The change has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It is a refactor. No devops command, option or message changes. Every spelling that a resolver reads gives the same address as before. The `public-api-egress` and `sandbox-egress` capabilities say nothing about how a numeric host is read, and their requirements still hold. The only results that change are for spellings that only Python read (`0b11.1`, `1_0.0.0.1`, `+1.2.3.4`) and spellings that only a resolver reads (`127。0。0。1`). A test covers them.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/validation.py` (the parser and its docstring), `src/devops_cli/security/reference_extractor.py` (one docstring sentence).
- Tests: `tests/core/test_numeric_hosts.py` (new), `tests/web_fakes.py`, `tests/security/test_reference_address_classes.py`, `tests/security/test_reference_extraction.py`.
- Callers of `parse_numeric_ip` that must keep their results: `is_loopback_host`, `_check_numeric_metadata` (twice) and `_is_numeric_host` in `src/devops_cli/core/validation.py`, and `network_target_address` (twice) in `src/devops_cli/security/reference_extractor.py`.

## Acceptance

The criteria of #2152, and the group of `tasks.md` that delivers each:

- Tests first for the octal and three-part forms and for `fe80::1%eth0`, each failing on a parser that drops the form: group 2. The issue names `validate_url(..., allow_private=False)`. That function is gone (#2845), so the tests call `is_loopback_or_private_host`, `is_loopback_host`, `is_cloud_metadata_host`, `is_cloud_metadata_ip` and `network_target_address`, which are its checks today.
- A test that `is_private_ip` returns `True` for a value that does not parse: group 2.
- `parse_numeric_ip` reads legacy forms with `getaddrinfo` and `ipaddress`; the three functions are deleted: group 3. The DNS seam of #1314 has not landed, so the call is direct.
- The repeated metadata check and the branches that cannot run are deleted: the check was already deleted by #2845 (nothing to do); the branches go with the three functions in group 3.
- The existing tests of the one-part, two-part and hex forms still pass: groups 1 and 3 run them. They are in `tests/security/test_reference_address_classes.py`, `tests/security/test_builtin_tools.py` and `tests/security/test_vulnerability_lookup.py`.
- No test starts a program or makes a DNS query: groups 1 and 3. A call with `AI_NUMERICHOST` makes no query, the hermetic floor in `tests/conftest.py` lets it through, and a test in group 3 shows that `parse_numeric_ip` sets the flag.
- `uv run devops ci` passes, the `constructs` row included: last task of group 3.

## Feasibility

Checked on 2026-11-01 at 9f3b7010, on Python 3.14.10 and glibc 2.43. These checks replace the 2026-10-24 check of the issue.

- The reader works. `socket.getaddrinfo(h, None, flags=socket.AI_NUMERICHOST)` gave `127.0.0.1` for `0177.0.0.1`, `127.1`, `127.0.1`, `2130706433`, `0x7f.1` and `0x7f000001`, and `gaierror` for `08.0.0.1` and `1.2.3.4 x`.
- Its error is not only `OSError`. For `"x" * 300` and `"é" * 70` the same call raised `UnicodeEncodeError`, a `ValueError` and not an `OSError`. The caller must catch `(OSError, UnicodeError)`, as `vet_addresses` in `src/devops_cli/http/egress.py` does. Today `parse_numeric_ip` returns `None` for both hosts, so group 2 pins them.
- `ipaddress.ip_address` must come first. `getaddrinfo("fe80::1%nope", None, flags=socket.AI_NUMERICHOST)` raised `gaierror` and `fe80::1%eth0` worked, because it needs the interface to exist. `ipaddress.ip_address` reads both without the host.
- The old parser and the new reader agree on every spelling that a resolver reads. A comparison script ran 46 spellings through both (script under `.data/agent/scratch/`, not committed). Ten differed. The old parser read these as addresses because Python `int` accepts them, and a resolver reads them as names: `0b11.1`, `0o17.1`, `+1.2.3.4`, `1_0.0.0.1`, `٣.0.0.1` and `١٢٧.١` (Arabic-Indic digits), and `127.0.0.1` with a space or a newline after it. The old parser read these as no address, and the resolver reads them as `127.0.0.1`: `127。0。0。1` (ideographic full stops) and `127.0.0.1` followed by a NUL character. `is_loopback_or_private_host` gave `True` for every spelling of both groups before and after a probe swap, so no refusal is lost. `is_loopback_host` follows the resolver in two cases: `١٢٧.١` is no longer loopback, and `127。0。0。1` is (the callers bind or dial the host, and the resolver reads it so).
- The premise holds on main. `git grep -n "_parse_part\|_combine_ipv4_parts\|_parse_legacy_ipv4" -- src` finds the three functions at `src/devops_cli/core/validation.py:193`, `:211` and `:227`. `parse_numeric_ip` is at `:242`. Their only callers are in `src/devops_cli/core/validation.py` and `src/devops_cli/security/reference_extractor.py:101,103`.
- The test gaps are real. A coverage run of `tests/core`, `tests/security`, `tests/http` and `tests/commands/test_valkey.py` reported these lines of `validation.py` as missed: `139-140` (`_parse_ip` on a value that does not parse), `142` (the zone-ID drop), `169` (`is_private_ip` on a value that does not parse), `203` (octal), `219-220` (three parts), `224` (the `return None` for a count other than 1 to 4) and `250-251` (the `except OSError, ValueError`).
- The two branches cannot run. `_combine_ipv4_parts` has one caller, `_parse_legacy_ipv4`, which passes 1 to 4 parts. `_parse_part` turns a `ValueError` of `int` into `None`, and `ipaddress.IPv4Address` gets a value of at most `0xFFFFFFFF`, so nothing raises `OSError` or `ValueError` out of `_parse_legacy_ipv4`.
- The zone-ID drop is testable. `is_cloud_metadata_ip("fd00:ec2::254%eth0")` gives `True`. With the drop removed it gives `False`, because the scope id changes the address hash.
- The repeated metadata check is gone. `git grep -n "_enforce_non_private_ssrf\|def validate_url" -- src` finds nothing. `git log -S_enforce_non_private_ssrf --oneline -- src` names 6ebc9683 (#2845, 2026-10-31). The name is now banned by `.ast-grep/rules/net-pre-flight-resolve.yml`.
- The `constructs` row allows the call. `git grep -n "getaddrinfo" -- .ast-grep` finds no rule on it. Only `socket.inet_aton`, `inet_ntoa`, `inet_pton` and `inet_ntop` are banned (`pyproject.toml:166-170`, TID251, #1107).
- The hermetic floor allows the call. `tests/conftest.py` `_guarded_getaddrinfo` (line 308) passes a call whose flags hold `AI_NUMERICHOST`, and `test_conftest_dns_guard_ai_numerichost` in `tests/core/test_validation.py:492` tests it.
- The change breaks tests that the issue does not name. A probe replaced `parse_numeric_ip` with the new reader and ran `uv run pytest tests`. These tests failed, and pass on the base: `tests/security/test_reference_address_classes.py::test_a_network_target_names_the_address_a_resolver_would_dial` (its stub raises on any `getaddrinfo` call), `tests/security/test_reference_extraction.py::test_reference_extraction_makes_no_dns_lookup` (same) and seven tests of `tests/commands/test_sandbox_networking.py` (the scripted resolver of `tests/web_fakes.py` counts the call and answers for a name even with `AI_NUMERICHOST`). With the scripted resolver changed to pass a flagged call to its fallback, the sandbox tests passed. Group 1 makes these three doubles ready before the code changes.
- Nothing newer covers the work. `uv run devops gh api 'search/issues?q=repo:dan-petty/devops-cli+parse_numeric_ip'` finds only #2152. No other change folder names `parse_numeric_ip`. #1314 (the DNS seam) is open.

## Existing Tool Considered

`socket.getaddrinfo` with `AI_NUMERICHOST` is the standard-library tool. It reads a numeric host with the rules of the C library and makes no DNS query. `ipaddress.ip_address` reads the IPv6 forms, including a zone ID, and classifies the result. No other library is needed. `socket.inet_aton` is not an option: TID251 bans it (#1107).

The change deletes `_parse_part`, `_combine_ipv4_parts` and `_parse_legacy_ipv4` from `src/devops_cli/core/validation.py`, and the branches in them that cannot run.

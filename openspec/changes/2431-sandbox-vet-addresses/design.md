# Design

## Decisions

- **The scrape keeps only the checks that read the URL.** `_validate_scrape_url` refuses a scheme that is not http or https, and a URL with no host. It does no address check, so its refusal no longer says "SSRF validation blocked". The factory client of the scrape checks the address at the connect, at the loopback level. An address refusal comes from the connect as `SSRFBlockedError`, and the scrape reports it as a failed scrape request.
- **Each builder calls `vet_addresses` at its level, with the port of the entry.** The public builder uses the public level. The local builder uses the private level. Then the local builder applies its own rule to each address: the address is private or loopback, and it is not link-local. This is the rule that the local builder applies to an IP literal or CIDR. The private level admits a link-local address that is not cloud metadata, such as 169.254.1.2. The local builder refused that address before, and it continues to refuse it. Thus each whitelist admits the same answers as before, and also refuses a scoped IPv6 answer.
- **The time-of-check gap fails closed.** The NetworkPolicy holds the addresses of one lookup. A later lookup in the pod can give a different address. The policy does not allow that address, so the pod cannot connect to it. Each builder says this in its docstring.
- **A refusal names the host.** The message of `SSRFBlockedError` masks the host (`tcp://<masked>:443`). A person who runs `devops sandbox network-policy` with three entries must know which entry the builder refused. So a builder changes a refusal of `vet_addresses` into a `SandboxValidationError` that names the host and gives the reason, with the refusal as its cause. A failed lookup raises `httpcore2.ConnectError`, which is not a `ValueError`, and the builder changes it in the same way.
- **The whitelist builders raise `SandboxValidationError`.** CONTRIBUTING.md forbids a bare `ValueError`. The four builder functions (`_resolve_public_dns`, `_resolve_public_host`, `_resolve_local_dns` and `_resolve_local_host`) raise `SandboxValidationError` for each refusal. It is a `ValueError`, so the pydantic validators and the command catch it as before.
- **The address blocks stay sorted.** `vet_addresses` returns the addresses in the order of the answers. A resolver can change that order from one lookup to the next. The builders sort the blocks, as before, so the same answers give the same manifest.
- **The metadata pre-check of `_resolve_local_host` stays.** It refuses a cloud metadata name or a numeric form of a metadata address, with no lookup. Some numeric forms, such as a decimal integer, are not IP literals that `ipaddress` parses, so without the pre-check they go to the lookup.
- **The refusal test skips the validators.** The test builds the configuration with `model_construct`, which runs no validator. So the refusal that it sees comes from the policy builder, not from the whitelist validators.

## Rejected alternatives

- **Let the `SSRFBlockedError` of `vet_addresses` go out of the builders unchanged.** It is a `ValueError`, so the command catches it. But its masked host does not tell the person which entry the builder refused. Also, a failed lookup still needs a change of type.
- **Give the local builder the loopback level.** The loopback level refuses a private answer, and a private address is the purpose of the local whitelist.
- **Use only the private level for the local builder.** The private level admits link-local addresses that are not cloud metadata. The local builder refuses those addresses as IP literals, and refused them from a lookup before. The issue keeps the level the same.
- **Keep the lookup of the public whitelist validator.** That lookup makes two lookups of each name, and part 5 (#2437) deletes `_resolve_host_ips`, which it calls. The builder makes the one lookup and refuses a non-public answer.
- **Return the blocks in answer order.** Two runs could give two manifests for the same answers, which makes a GitOps diff for no change.

## Non-goals

- `sandbox/probe.py`, which already dials through the factory at the private level.
- The tests that patch `_resolve_host_ips` to check the container engine endpoint (`tests/test_sandbox_lifecycle.py`). Part 5 (#2437) changes that check.
- The deletion of `_resolve_host_ips` and `_enforce_non_private_ssrf` in `core/validation.py`. Part 5 deletes them.
- The general statement that every HTTP client is checked at the connect. Part 5 writes it when it is true.

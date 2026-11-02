# Design

## Decisions

- **Use Python's `ipaddress` properties as the maintained source.**: The standard library is public, maintained and follows the IANA special-purpose registries. It adds no dependency.
- **Keep the ISATAP and IPv4-compatible rules with RFC comments and tests.**: `ipaddress` has no named property for these two rules.
- **Deliver after #2152.**: #2152 changes `parse_numeric_ip` in the same module, so the two changes touch the same lines.
- **Delete the hand-kept block-list constants.**: The constants copy a private module and can drift from upstream.
- **Use an offline table test over `ipaddress` values.**: The test reaches no network, no cluster and no real scanner.

## Rejected alternatives

- **Use the private module `pydantic_ai._ssrf` directly.**: The issue states that the module has no API promise, and the inputs show the docstring names it as the source of the copy.
- **Keep the hand-kept block list and update it on each upgrade.**: The issue states that the copy can drift from upstream and that the owner's rule requires maintained libraries.
- **Add a new third-party SSRF library.**: The standard library `ipaddress` covers the need, so a new dependency adds cost without a new result.
- **Use only `ipaddress.is_private`.**: `is_private` does not cover every non-public special-purpose range. `is_global` follows the IANA registries.

# Proposal

## Why

Issue #3142: the hardening audit found that the defect fix #3141 (issue #3140) added its guardrail to a test and to `k8s/README.md`, and to none of the declared hardening surfaces. The lesson of #3140 belongs in `SECURITY.md` rule 12, which owns the rules of the hosted gateway groups: a Claude group needs the two native structured output flags, or a structured call becomes a forced tool call that Sonnet 5.5 refuses.

## Feasibility

- `git grep -n "supports_native_structured_output" -- SECURITY.md` prints nothing on `origin/main`.
- `SECURITY.md` rule 12 states the other rules of the hosted groups, and the test `test_the_hosted_groups_call_providers_with_optional_keys_and_join_no_pool` holds them.

## Existing Tool Considered

No external tool covers this. The change adds one sentence to one document.

## What Changes

- `SECURITY.md` rule 12 names the three settings of a Claude group and the test that holds them.
- The change has no spec delta: no `devops` command, option or message changes.

## Impact

- Documentation only.

# Proposal: #5082

## Why

`rejects()` accepts an ADR rejection only when every option that names the tool says `rejected` or
`not chosen`. ADR 0018 lists `gVisor` and `nsjail` without those words, and ADR 0024 lists IBM
Carbon and GitHub Primer the same way, so the alternatives job drops correct rejections. #3827
then keeps a `covers` verdict for a tool that ADR 0018 did not choose. Closes #5082.

## What Changes

- `rejects()` inverts the rule: an ADR rejects a tool when an option names it and no chosen or
  adopted option names it. The title still excludes a rejection.
- A chosen or adopted option wins even when it also says `not chosen` or `not adopted`.
- Tests replay the #4661 census cases, the mixed-marker case and the deferred-option case.
- `docs/roadmap/alternatives.md` and the `roadmap-alternatives` specification state the rule.

## Capabilities

### Modified

- `roadmap-alternatives`: the confirmation of a `rejected` proposal follows the inverted rule.

## Impact

The alternatives job keeps the four true rejections of the census and loses none. ADR 0010 still
does not reject OpenSpec. A deferred option counts as rejected, and the check runs again when the
ADR changes.

## Feasibility

Confirmed against the issue and the code: `rejects()` in `src/devops_cli/roadmap/adr.py` holds
the marker test, and `_options()` already gives each option's markdown. The real ADR files hold
the census cases, so the replay test needs no fixture.

## Existing Tool Considered

No open tool or library covers the need. The alternatives check of 2026-11-15 returned `none`: only
generic ADR authoring and parsing projects exist, and none supplies this project's rejection rule.
The change corrects the project's own rule in about 1,500 tokens to build.

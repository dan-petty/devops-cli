# Design

## Decisions

### Invert the rule around the chosen option

`rejects()` returns false when the title names the tool. Otherwise it collects the options that
name the tool. When none names it, the ADR does not reject it. When a chosen or adopted option is
among them, the ADR chose the tool and rejects nothing. Otherwise the option is one the decision
did not take, so the ADR rejects the tool. This matches the `Considered Options` section of an ADR
better than a list of rejection words.

### A chosen marker wins over a not-chosen phrase

`_says_chosen()` removes `not chosen` and `not adopted` from an option, then looks for `chosen` or
`adopted`. An option that says both is chosen, which is the safe result: it cannot reject a tool
that the ADR adopted.

### A deferred option counts as rejected

ADR 0018 says of `kubernetes-sigs/agent-sandbox` that the record does not measure it. No chosen or
adopted option names the tool, so the rule rejects it. A later ADR or a re-measurement changes the
answer, and the check runs again when the ADR changes.

### Replay the real ADR files

The replay test reads the ADR files in `docs/adr/` and asserts the four census rejections and the
ADR 0010 exclusion. A synthetic option alone would not prove the rule against the records that
showed the defect.

## Rejected alternatives

- **Keep the rejection words:** it drops the correct rejections of ADR 0018 and ADR 0024.
- **Reject only when the title names the tool:** it ignores the options and loses the census.
- **Treat a mixed-marker option as rejected:** it can reject a tool that the ADR adopted.
- **Exclude the deferred option:** it needs a fragile phrase list and delays a correct rejection.

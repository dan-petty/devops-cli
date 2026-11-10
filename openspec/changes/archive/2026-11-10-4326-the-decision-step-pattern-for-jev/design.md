# Design

## Decisions

- **The record is an ADR and a spec.** The ADR holds the reasons, the candidates and the bars. The spec holds the rules that a test can assert. Both follow `docs/adr/0018-*` and `openspec/specs/ai-ask-jev`.
- **Seven rules.** A decision point and not a generation point; tools extract the evidence into a short digest that Jev judges; many small questions in one request; thresholds fitted on labelled data with a fixed split and a swapped repeat; action bands; shadow first and fail open; a Jev answer is evidence and never the only control. Each rule answers a failure of the three trials.
- **The pilots.** Pilot 1 is the verify screen, because its outcome is binary, the golden set labels it, and the reviewer is the fallback. Pilot 2 is the failure-class tail, because it is a closed choice with a known default. Pilot 2 waits, so that the shared parts of pilot 1 are proved first.
- **The bar and its oracle.** A bar above the share of cases that need no run cannot be met. The ADR requires the oracle to be reported and checked before the first fit.
- **Shared parts, not a framework.** The ADR names one small module for the typed question set, the request builder, the fitted thresholds and bands, the log record and the fail-open rule. The code is in the pull request of #4282.

## Rejected alternatives

- **Use Jev as the model of every step that a cheaper model could serve.** Rejected: the completeness check (28% false holds, 43% recall) and the intake labels (0 of 3 duplicates) show that Jev does not write and does not read a long text.
- **Guess a threshold and tune it after a switch is on.** Rejected: the guessed thresholds of #4323 and #4282 are the cause of their failures.
- **One rule for the cuts, fixed in advance.** Rejected: questions differ in base rate, but a half of 24 cases cannot fit nine cuts. The fit runs both ways and the report shows both.
- **Let Jev replace the reviewer.** Rejected: the reviewer reads the repository with tools and gives a quote, and a finding that can stop a plan needs a quote.
- **Wait for a better Jev.** Rejected: the pattern holds for the next version, and the fit repeats on its data.

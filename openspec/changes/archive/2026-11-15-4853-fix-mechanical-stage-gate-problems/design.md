# Design

## Decisions

- **In-process rewrite before model returns**: Apply mechanical findings as a deterministic in-process rewrite before sending a refused proposal back to the model.
- **Pass bound**: Apply at most two mechanical rewrite passes to avoid infinite loops and catch cascading findings.
- **Counter metric**: Record `devops_cli_roadmap_fix_checks_total` with `site="stage.gate"` and `path="mechanical"` on each rewrite.

## Rejected alternatives

- **Model prompt instructions**: Rejected because each model round costs about 0.31M prompt tokens and adds latency for deterministic edits.
- **Separate job**: Rejected because a separate job introduces cluster scheduling overhead and network roundtrips for edits requiring no model call.
- **Unbounded rewrite loops**: Rejected to prevent cycles when unexpected finding interactions occur.

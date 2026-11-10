# Design

## Decisions

- **The template follows the live value for `analysis`.** The owner decided on 2026-11-10 to move the slot back to DeepSeek and to try Sonnet later. The template is what a render writes, so it must hold the decided value.
- **An explicit `stage` entry.** The live ConfigMap has one, and the owner chose it. Without it the task `stage` takes the model and the window of `analysis`, so a later Sonnet trial in `analysis` would also move the stage job. The template now sets both.
- **The window is 256000.** It is the smallest window that an fp8 provider of the group offers, and the value the other slots use. The plan run needs about 38000 tokens for its first request and ends its tools at three quarters of the window.
- **The ladder stays.** The two-tier `edit` and `repair` ladders of the template came from #4275 on purpose (its change names "two-tier implement ladders"). The live ConfigMap has one tier. Which one is right needs the owner, so a separate issue holds it.
- **Live-only values stay out.** `service.repos`, the App identifiers, `drain_timeout_seconds`, `poll_interval_seconds` and `github_requests_per_hour` are deployment values. The template keeps its placeholders and defaults.

## Rejected alternatives

- **Remove the `stage` entry from the live ConfigMap.** Rejected: the cluster is not part of this change, and the live entry is the owner's choice.
- **Keep the Sonnet value in the template as a documented trial.** Rejected: a render would then undo the decision of 2026-11-10.

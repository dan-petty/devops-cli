# Design

## Decisions

- **One label for each verdict and kind.** The verdicts are workflow labels, because the roadmap code reads them (#4652). `plan/needs-fix` already means "the plan needs a fix": the stage review, the row `plan_drift` and a vet set it, and the step fix-plan repairs the plan and removes it. So it is the needs-fix verdict of a plan, and a plan never gets `verdict/needs-fix`. A delivery has no such label, so `verdict/needs-fix` is its needs-fix verdict. The other four labels apply to both kinds.
- **The first verdict comes from the label events.** The step fix-plan removes `plan/needs-fix` after a repair, and a vet can add `verdict/mergeable` after a fix. The labels of today lose the first verdict, so the read takes the `LABELED_EVENT` items of the timeline, which GitHub keeps after an unlabel. The first event whose label is a verdict label of the kind gives the verdict. A later event keeps the history and does not change the score.
- **One GraphQL search, not one search for each kind.** One search `is:pr author:app/<slug> created:>=<window start>` gives both kinds, and the title splits them. The same request gives the label events, so the read sends one request (1 point) for each 100 pull requests. A REST search gives the labels of today only, and the events endpoint costs one request for each pull request (113 on 2026-11-16). A search with more results than GitHub returns (1000) stops the report, so a short read never reads as all.
- **A verdict scores the job that opened the pull request.** A plan pull request scores stage and a delivery pull request scores implement. "Discard plan" is a failure of stage, and "discard implementation" a failure of implement (owner table). A delivery whose plan cannot be built gets "discard plan": the report shows it, and the implement score leaves it out, as it leaves out issue changed.
- **One shared setting for the partial score.** `roadmap.verdict_partial_score` (0 to 1, default 0.5) gives the score of needs fix for both jobs. The owner gave one value, and a job-level setting can come when the values must differ.
- **The shares count the pull requests with a verdict.** The share of a verdict is its count over the pull requests with a verdict. The open pull requests are a count of their own, so the share does not fall while the vets work.
- **No slug, no read.** The bot login comes from `service.github_app.slug`. With no slug there is no bot, so the report reads no verdict and its text names the setting. The Loki part of the report does not change.

## Rejected alternatives

- **A new `verdict/needs-fix` on a plan beside `plan/needs-fix`.** Two labels would give one meaning, and a vet who sets only one of them either queues no repair or records no verdict.
- **The labels of today, with an order of the verdicts.** On 2026-11-16, 38 of 100 bot pull requests got `plan/needs-fix` at some time, and the step fix-plan removes it after a repair. An order such as "discard before needs fix before mergeable" also gives a wrong first verdict for "mergeable, then issue changed".
- **The issue events endpoint for each pull request.** It gives the same events at one REST request for each pull request: 113 requests for the 7-day window of 2026-11-16, against 2 GraphQL requests.
- **A merge as the success of an attempt.** The first version of #5968 gave a lagging merge credit. The owner replaced it with the verdicts on 2026-11-16, because a merge after a fix is not a success of the attempt.

# Design

## Decisions

- **Put both alerts in a new group `crawl4ai`.**: The group `roadmap-service-activity` holds only rules that select the job of the Service, and a test enforces it. The Deployment rule reads kube-state-metrics, so a group of its own keeps that test and gives the Crawl4AI rules one fixture.
- **Count a failure as any `result` other than `ok`.**: The client sets `result` to `ok`, to the HTTP status of a refused fetch, or to `error`. A negative matcher counts a new status with no change of the rule.
- **Fire above one half of the fetches and at least 5 failures, in one hour.**: One failed fetch must not fire. A refine or alternatives run reads at most 3 pages, so 5 failures need several runs. A page that fails for its own reason (a site that blocks or a slow page) is normal, and a ratio above one half separates it from a broken service. The rule is warning severity and has no wait (`for: 0m`), because the hour window already smooths it.
- **Read a series that starts in the hour from its first value.**: The counter comes over OTLP and a series starts at its first fetch, so `increase()` alone would miss the first value (#2505). The rule uses the same pair of terms as the other rules of the Service.
- **Select `job="roadmap-service"`.**: A fetch from a workstation (`devops ai fetch-page`) has `job="devops-cli"` and does not show the state of the cluster.
- **Stay quiet with no `crawl4ai.url`.**: The Service sends no fetch then, the counter has no series and the division gives no sample.
- **Fire the Deployment rule only while `spec.replicas` is above 0.**: A person may set the Deployment to 0 replicas to stop the pod. That is not a fault.
- **Wait 15 minutes for the Deployment rule.**: The first start pulls an image of 2.3 GB, and the Recreate strategy stops the old pod before it starts the new one.

## Rejected alternatives

- **Scrape the `/metrics` of Crawl4AI.**: The route needs the bearer token, and the issue forbids it.
- **A ratio of the total fetches, not of the failed count, as the minimum.**: The issue asks that one failure does not fire. A minimum of failures says that directly.
- **Alert on `RoadmapServiceUnavailable` style `replicas_unavailable`.**: That series is 0 for a Deployment that has no pod yet, and the available count is the direct signal.

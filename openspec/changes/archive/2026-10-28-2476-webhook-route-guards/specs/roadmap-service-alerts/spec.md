## ADDED Requirements

### Requirement: The webhook route has its own alert group
The rule group `roadmap-service-webhooks` in `k8s/monitoring/prometheus-values.yaml`, separate from the group `roadmap-service`, SHALL hold the warning alert `RoadmapServiceWebhooksRejected`. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert.

#### Scenario: The rule names the Service
- **WHEN** a test reads the selectors of the group
- **THEN** each selector of `devops_cli_service_webhook_deliveries_total` has `job="roadmap-service"` and `outcome="rejected"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `k8s/README.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: A burst of rejected webhook deliveries warns
`RoadmapServiceWebhooksRejected` SHALL fire when the webhook route of the Service rejected more than 20 deliveries in 15 minutes, also when a series of rejected deliveries started in the 15 minutes. It SHALL NOT count the deliveries of another outcome or of another job.

#### Scenario: A new series of rejected deliveries
- **WHEN** `promtool test rules` evaluates a new series of rejected deliveries that grows by 5 each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet while the series is at 20 or less, and fires when it gets to 25, and the summary gives 25

#### Scenario: A few rejected deliveries of an older series
- **WHEN** `promtool test rules` evaluates a series of rejected deliveries from before the 15 minutes that grows by 1 each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet

#### Scenario: A burst in an older series
- **WHEN** the same series then grows by 3 each minute
- **THEN** `RoadmapServiceWebhooksRejected` fires

#### Scenario: Accepted deliveries and another job
- **WHEN** `promtool test rules` evaluates 10 accepted deliveries of the Service each minute, and 10 rejected deliveries of the job `devops-cli` each minute
- **THEN** `RoadmapServiceWebhooksRejected` stays quiet

# crawl4ai-alerts Specification

## Purpose
The alert rules that tell an operator when the roadmap Service cannot read page text through Crawl4AI: when most of its page fetches fail, and when the Crawl4AI Deployment has no available replica. Without them the refine and alternatives jobs lose their page text with no visible sign.

## Requirements

### Requirement: The Crawl4AI alerts have their own rule group
The rule group `crawl4ai` in `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold the warning alerts `Crawl4AIFetchesFailing` and `Crawl4AIUnavailable`. promtool SHALL accept them. Each description SHALL point to the section "Crawl4AI" of `k8s/README.md`, and that section SHALL list each alert.

#### Scenario: The group and the README
- **WHEN** a test reads the group and the section "Crawl4AI" of `k8s/README.md`
- **THEN** both alerts have severity `warning`, name the section in the description, and appear in the section

### Requirement: Failed fetches warn
`Crawl4AIFetchesFailing` SHALL fire when, in the last hour, at least 5 fetches of `devops_cli_crawl4ai_fetches_total{job="roadmap-service"}` had a `result` other than `ok` and those failed fetches were more than half of all its fetches. It SHALL count a series that started in the hour from its first value, and SHALL select the job of the Service only.

#### Scenario: Most fetches fail
- **WHEN** `promtool test rules` evaluates 60 fetches `ok`, 60 with `result` `504` and 60 with `result` `error` in the hour
- **THEN** `Crawl4AIFetchesFailing` fires and its summary names two thirds

#### Scenario: A new series of failures
- **WHEN** `promtool test rules` evaluates new series whose first values are 8 failed fetches and 2 fetches `ok`
- **THEN** `Crawl4AIFetchesFailing` fires, and it stays quiet once an hour passed with no new sample

#### Scenario: Fewer than 5 failures
- **WHEN** `promtool test rules` evaluates a new series with 3 failed fetches and no fetch `ok`
- **THEN** `Crawl4AIFetchesFailing` stays quiet

#### Scenario: A small share of failures
- **WHEN** `promtool test rules` evaluates 600 fetches `ok` and 60 failed fetches in the hour
- **THEN** `Crawl4AIFetchesFailing` stays quiet

#### Scenario: A workstation and no series
- **WHEN** `promtool test rules` evaluates failed fetches with the job `devops-cli` and no series with the job `roadmap-service`
- **THEN** `Crawl4AIFetchesFailing` stays quiet

### Requirement: The text of the fetch alert names the label and the logs
The description of `Crawl4AIFetchesFailing` SHALL name the label `result` and the commands `kubectl -n devops logs deployment/roadmap-service` and `kubectl -n devops logs deployment/crawl4ai`.

#### Scenario: A person reads the alert
- **WHEN** a test reads the summary and the description of the alert
- **THEN** they name the label and both commands

### Requirement: A Deployment with no available replica warns
`Crawl4AIUnavailable` SHALL fire after 15 minutes in which `kube_deployment_status_replicas_available` of Deployment `devops/crawl4ai` is below 1 while `kube_deployment_spec_replicas` of the same Deployment is above 0. It SHALL select the namespace `devops` and the Deployment `crawl4ai` only.

#### Scenario: No replica for 15 minutes
- **WHEN** `promtool test rules` evaluates an available count of 0 and a wanted count of 1 for 20 minutes
- **THEN** `Crawl4AIUnavailable` stays quiet at 10 minutes and fires after 15 minutes, with the labels `namespace` and `deployment`

#### Scenario: A Deployment set to 0 replicas
- **WHEN** `promtool test rules` evaluates an available count of 0 and a wanted count of 0
- **THEN** `Crawl4AIUnavailable` stays quiet

#### Scenario: Another Deployment
- **WHEN** `promtool test rules` evaluates an available count of 0 for Deployment `roadmap-service`
- **THEN** `Crawl4AIUnavailable` stays quiet

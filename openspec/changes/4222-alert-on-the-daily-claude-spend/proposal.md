# Proposal

## Why

No alert fires on the Claude spend (#4222). On 2026-11-09 a stage task on `claude-sonnet-5-5` spent about 21 USD per hour while every round failed, and nobody saw it until the owner read the cost page. The 24 hour Anthropic costs of the owner from 2026-11-03 to 2026-11-08 were 1.65, 1.72, 3.74, 0.39, 0.13 and 0 USD. The cost of 2026-11-09 was about 58 USD after the failed burst. The budgets per item and per day (#3066) count tokens and seconds, and they send no alert on dollars. The counter `devops_cli_ai_spend_usd_total` priced a hosted agent run as local spend at 0 USD until #3665, so an alert on it stayed quiet. #3665 is merged, so the counter now carries the spend.

## What Changes

- A new rule group `ai-spend` in `k8s/monitoring/prometheus-values.yaml` holds two warning alerts on `devops_cli_ai_spend_usd_total`.
- `ClaudeSpendDailyHigh` fires when `sum(increase(devops_cli_ai_spend_usd_total{model="claude-sonnet-5-5"}[24h]))` is above 15 USD.
- `HostedSpendDailyHigh` fires when `sum(increase(devops_cli_ai_spend_usd_total[24h]))` is above 25 USD. A local request adds 0 to the counter, so this sum is the spend of the hosted models.
- Both alerts sum over every job, so a run from a workstation (`job="devops-cli"`) and a run of the Service (`job="roadmap-service"`) count together.
- Both alerts fire at once (`for: 0m`): the window of 24 hours is the smoothing, and a burst of 21 USD per hour passes 15 USD in under one hour.
- `k8s/README.md` lists both alerts in the alert table, with the first step: read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job.
- The promtool fixture `tests/fixtures/prometheus_rules/ai_spend_tests.yaml` and the tests in `tests/prometheus/test_k8s_monitoring_alerting.py` pin the rules.
- The change is a manifest that operators observe, so it carries the spec delta for the new capability `ai-spend-alerts`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-spend-alerts`: The alert rules on the daily USD spend of Claude and of all hosted models

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/monitoring/prometheus-values.yaml`
- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/ai_spend_tests.yaml` (new)
- Documents: `k8s/README.md`

## Feasibility

All checks ran on 2026-11-09 against the live stack.

- The counter exists on `main`: `AI_SPEND_USD_TOTAL` in `src/devops_cli/telemetry/instruments.py`. #3665 is merged (PR #4231, "price a hosted group call by the asked model"), and the description of the counter says that its `model` label is the model that the client asked for.
- A read-only Prometheus query (datasource `prometheus`) of `devops_cli_ai_spend_usd_total` shows series with the labels `job`, `instance`, `model`, `operation`, `provider` and `server`. The counter has no `local` label (the token counter has it), so the rules select on `model` only. There are series with `model="claude-sonnet-5-5"` for `job="roadmap-service"` and for `job="devops-cli"`, and their `increase` over 24 hours was 56.66 USD for the Service. That is near the 58 USD of the burst, so the series carries a Claude price now.
- The live Service pod started at 15:33Z, after the merge of #4231 at 14:32Z. The image is `service:latest` by digest, and the digest cannot be mapped to a commit from the cluster, so this change does not prove that the running image holds #4231. The rules are correct either way: with the old image the spend reads low and the alerts stay quiet, as the issue says.
- The series of the Service resets when its pod restarts. `increase` adds the value before each reset, and the fixture pins that case.
- The pinned promtool (`promtool test rules`) passes the unit tests of both rules. Before the rules existed, the new tests failed on `main` because the group `ai-spend` did not exist.
- The series `litellm_spend_metric_total` is not used. The two series would count the same spend twice.
- The thresholds: the highest normal day of the owner is 5.59 USD (the issue), and the burst of 2026-11-09 is about 58 USD. 15 USD for `claude-sonnet-5-5` and 25 USD for all hosted models are between the two. A month of data will tune them (#4222).

## Existing Tool Considered

Prometheus rules in the existing values file, tested with promtool, as for the other alerts. No new tool and no new code. The LiteLLM `max_budget` per key stops a key at a limit, but it sends no alert. The change deletes no code.

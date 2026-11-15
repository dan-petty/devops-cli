# Design: #4545

## Context

The gateway's ServiceMonitor scrapes `/metrics/` every 15 s. Each `litellm_*` series carries
`client_ip` and `user_agent`, and the dashboard queries group by `status_code`, `end_user`,
`model_id` and `api_base` only.

## Decisions

- One `labeldrop` rule for each label name: the name is visible in the manifest and in the check
  without a regex.
- The check reads the raw ServiceMonitor, so the two rules and the untouched port, path and
  interval fail together.
- The dashboard check reads every `expr` of the two dashboards and the alert check reads every
  `expr` of the alerting rules, so a later query that needs a dropped label fails the row.
- The offline checks read the manifests. The live query
  `count by (__name__) ({__name__=~"litellm_.*", client_ip!=""})` is a post-merge check, because
  no offline test reaches Prometheus.

## Risks

- The drop applies to the whole endpoint, so a later item that needs caller identity must add a
  bounded label. The refine records that cost.

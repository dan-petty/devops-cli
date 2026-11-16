## MODIFIED Requirements

### Requirement: The metrics row counts the failed deliveries of the hooks
Each time the metrics row of the Service runs, it SHALL read the active hooks of its repository and the newest 100 deliveries of each active hook through `gh api`, so that the request budget of the Service counts each read. It SHALL set the gauge `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to the deliveries whose status code is not 2xx in the window: 15 minutes, or `roadmap.metrics.interval_minutes` plus 2 when that is longer.

#### Scenario: Two refusals in the window
- **WHEN** the newest page of deliveries of the hook holds two 403 answers of the last 15 minutes, one 202 answer and one 403 answer from before the 15 minutes
- **THEN** the gauge of code `403` is 2, the read sends one request for the hooks and one for the deliveries of the hook

#### Scenario: Two hooks and an inactive hook
- **WHEN** two active hooks have failed deliveries with the codes 403, 502 and 504, and an inactive hook has a 403
- **THEN** the gauge adds the deliveries of the two active hooks by code, and the inactive hook gets no request

#### Scenario: A slower metrics row
- **WHEN** `roadmap.metrics.interval_minutes` is 26, and the newest page holds a 403 answer of 20 minutes ago and one of 30 minutes ago
- **THEN** the window is 28 minutes, and the gauge of code `403` is 1

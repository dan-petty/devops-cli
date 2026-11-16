## MODIFIED Requirements

### Requirement: The metrics row counts the failed deliveries of the hooks
Each time the metrics row runs, it SHALL read through `gh api` the active hooks of its repository and the failed deliveries of each (`status=failure`), 100 a page. It SHALL count from its last good read of the repository, or 15 minutes before the read when that is earlier, follow each `Link` until a delivery is older, read at most 10 pages of a hook, and set `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to the deliveries that are not 2xx.

#### Scenario: Two refusals in the window
- **WHEN** the first read of a process finds two 403 answers of the last 15 minutes, one 202 answer and one 403 answer from before the 15 minutes
- **THEN** the gauge of code `403` is 2, the read sends one request for the hooks and one for the failed deliveries of the hook

#### Scenario: Two hooks and an inactive hook
- **WHEN** two active hooks have failed deliveries with the codes 403, 502 and 504, and an inactive hook has a 403
- **THEN** the gauge adds the deliveries of the two active hooks by code, and the inactive hook gets no request

#### Scenario: A gap longer than the window over two pages
- **WHEN** a read comes 30 minutes after the last good read, and the failed deliveries since then fill one page and go on in the next
- **THEN** the read follows the link to the second page, counts each failed delivery since the last read, counts none from before it, and asks for no third page

#### Scenario: A read that fails
- **WHEN** a read fails between two good reads
- **THEN** the next read counts from the last good read

#### Scenario: A gap of hours
- **WHEN** the failed deliveries since the last good read fill more than 10 pages
- **THEN** the read reads 10 pages and logs a warning that names the hook

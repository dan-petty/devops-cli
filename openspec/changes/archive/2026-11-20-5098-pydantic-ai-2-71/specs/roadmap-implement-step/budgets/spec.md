## MODIFIED Requirements

### Requirement: The limits that end an implement step are settings
The implement step SHALL read each limit that ends its run from `roadmap.implement` when the step starts. The default of each new setting SHALL be the value of the constant that it replaces, so a step with no configuration does not change. The file tools of the harness SHALL take `tool_retries` in place of their own count.

#### Scenario: No configuration
- **WHEN** no source sets `max_requests`, `max_tool_calls`, `tool_retries`, `max_refusals`, `max_consecutive_refusals`, `model_resends`, `extension_calls` and `extension_max_refused`
- **THEN** they are 500, 1500, 5, 30, 3, 1, 20 and 3, the values of the constants that they replace

#### Scenario: The refusal and retry limits of a setting
- **WHEN** `max_consecutive_refusals` is 5, `max_refusals` is 7 and `tool_retries` is 2
- **THEN** 5 refusals in a row stop a step, 7 refusals between accepted calls stop a step at its eighth request, and a third call of `read_file` in a row with no `path` argument stops a step

#### Scenario: No resend and a small request limit
- **WHEN** `model_resends` is 0 and `max_requests` is 2
- **THEN** a request that fails with a 400 inside a stream is not sent again, and a model that reads in every reply gets 2 requests

#### Scenario: The window of the extension
- **WHEN** `extension_calls` is 10 and `extension_max_refused` is 5
- **THEN** the digest of the tool log counts the last 10 calls, and a step at its token budget with 5 refused commands in them gets the extension

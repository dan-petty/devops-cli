## ADDED Requirements

### Requirement: A build_agent request names its served backend
The spend hook of `build_agent` SHALL pass `served_by` to `track_request_spend`, so the backend breakdown counts the request and the price follows the backend that served it.

#### Scenario: A request with a served backend
- **WHEN** an agent of `build_agent` runs on a model whose `served_by` is a backend URL
- **THEN** the lifetime report holds one backend entry with that URL and one request

#### Scenario: A hosted backend behind the gateway
- **WHEN** the `served_by` is a hosted API URL
- **THEN** the request is priced at the model that the reply names, not at zero

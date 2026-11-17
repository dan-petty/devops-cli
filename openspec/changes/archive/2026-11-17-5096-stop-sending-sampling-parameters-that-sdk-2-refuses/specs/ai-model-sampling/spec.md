## MODIFIED Requirements

### Requirement: Claude provider capability-driven sampling parity

The system SHALL send `temperature` and `top_p` on both streamed and unstreamed Claude requests
only when the installed Anthropic SDK major version is below 2, the model declares sampling
support, and neither adaptive thinking nor `use_model_sampling` is active. SDK 2 and later SHALL
omit `temperature`, `top_p` and `top_k`.

#### Scenario: Claude model declaring sampling support transmits identical parameters

- **WHEN** a Claude model declares sampling support, adaptive thinking is disabled, and the
  installed SDK major is below 2
- **THEN** streamed and unstreamed requests carry identical `temperature` and `top_p` values

#### Scenario: Claude model without sampling support omits sampling parameters

- **WHEN** a Claude model does not declare sampling support
- **THEN** streamed and unstreamed requests omit `temperature` and `top_p`

#### Scenario: Anthropic SDK 2 omits the refused parameters

- **WHEN** the installed SDK major is 2, the model declares sampling support, and the fake HTTP
  seam returns HTTP 400 for `temperature`, `top_p` or `top_k`
- **THEN** the Claude call succeeds and the captured body holds none of the three fields

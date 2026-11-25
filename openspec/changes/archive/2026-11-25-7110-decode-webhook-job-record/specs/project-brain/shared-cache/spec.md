## ADDED Requirements

### Requirement: Webhook issue caching decodes job records
`issue_from_event` SHALL decode the split job record dictionary through `decode_job_record` before constructing `IssueRecord`, normalizing integer `implement.repair_rounds` values and filtering unknown or malformed record keys.

#### Scenario: An issue webhook carries integer repair rounds and an unknown key
- **WHEN** a signed `issues` or `issue_comment` webhook arrives for an issue whose body holds `implement.repair_rounds` as an integer and an unknown or malformed key
- **THEN** the webhook returns HTTP 202 and the cached `IssueRecord.job_record` holds the string value for `implement.repair_rounds` without raising a validation error

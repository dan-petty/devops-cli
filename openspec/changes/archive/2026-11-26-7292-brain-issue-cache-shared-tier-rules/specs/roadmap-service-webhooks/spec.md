## ADDED Requirements

### Requirement: A delivery gives the visibility of its repository
The model `WebhookRepository` SHALL parse the optional field `private` of the repository of a delivery. The roadmap consumer SHALL take the visibility of the repository from that field, else from the answer of the visibility check that the process holds, and SHALL take it as unknown when it has neither. It SHALL write the issue of a private repository only when the process sends the ACL user `sweep`, and SHALL send no GitHub request for the visibility.

#### Scenario: A delivery of a private repository writes no key
- **WHEN** the roadmap consumer receives a signed `issues` delivery whose payload holds `private: true`, and an own-write delivery of the same repository, and the process sends no ACL user
- **THEN** the first delivery is answered with HTTP 202 and wakes the row, the `valkey_server` fake holds no key, and `devops_cli_brain_writes_total{store="issue",result="private"}` rises by two

#### Scenario: A delivery of a private repository under the sweep user
- **WHEN** the roadmap consumer receives a signed `issues` delivery whose payload holds `private: true`, and the process sends the `sweep` user
- **THEN** the `valkey_server` fake holds the key `valkey:roadmap:v1:issue:<owner>/<name>:<number>` of the issue

#### Scenario: A delivery with no visibility
- **WHEN** the roadmap consumer receives a signed `issues` delivery whose payload holds no `private`, first in a process that holds no visibility answer and then after a public answer of the visibility check
- **THEN** each delivery is answered with HTTP 202, the first writes no key and counts `devops_cli_brain_writes_total{store="issue",result="unknown"}`, and the second writes the key of the issue

## MODIFIED Requirements

### Requirement: The roadmap consumer writes the cached issue before it wakes the lane
The roadmap consumer MUST write the issue of a subscribed `issues` event into the project brain from the event payload before it enqueues the wake of a row, and MUST send no GitHub request for that write. It MUST write nothing for a repository that the shared tier does not take from the process, and MUST wake the row as before.

#### Scenario: A labeled issue event writes the entry and wakes the row
- **WHEN** The roadmap consumer receives an `issues` event with action `labeled` for an issue of a Service repository whose payload holds `private: false`.
- **THEN** The fake tier holds the new label set with the event time, and the fake lane trigger records one wake for the due row.

### Requirement: Own-write issue deliveries refresh the cached issue without waking a lane
When `roadmap_consumer` refuses an `issues` delivery as an own write of the App bot, it SHALL refresh the cached issue from `payload.issue` when the shared tier takes the repository from the process and no entry exists, the stored entry has no `updated_at`, or `payload.issue.updated_at` is strictly greater than the stored one. It SHALL still return `CONST_SERVICE_STATUS_OWN_WRITE`, count outcome `self`, make no GitHub request, and wake no lane or scoped update.

#### Scenario: A newer own-write issue webhook updates the brain entry
- **WHEN** `valkey-devops` holds an issue of a public repository cached at `T0` with `Status: In Progress`, and an App-bot `issues` webhook arrives for that issue with `updated_at` at `T1 > T0` and `Status: In Review`
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}`, counts outcome `self`, wakes no lane, and updates `valkey-devops` to `Status: In Review`

#### Scenario: A stale or same-second own-write webhook does not clobber a fresher cached entry
- **WHEN** `valkey-devops` holds an issue of a public repository cached at `T1`, and an App-bot `issues` webhook arrives with `updated_at <= T1` (or with `comment` present or `pull_request` set)
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}` and keeps the existing brain entry unchanged

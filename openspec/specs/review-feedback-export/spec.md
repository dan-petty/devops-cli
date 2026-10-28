# review-feedback-export Specification

## Purpose
Which findings and verdicts `devops review export-feedback` appends to the feedback dataset: each finding of a reviewed subject once, with the newest verdict a person gave it in any session of that subject.

## Requirements

### Requirement: Each finding of a subject is exported once
The export SHALL append one record for each finding of a subject that the sessions of that subject share by fingerprint v2, whatever the number of sessions. Each record SHALL carry its `subject_key` and `fingerprint_v2`.

#### Scenario: Three sessions of one subject
- **WHEN** three sessions of one subject each hold the same two findings, and the export runs with `--status ALL`
- **THEN** it appends two records, one for each fingerprint v2, each with the subject key of that subject

#### Scenario: The CLI reports the count
- **WHEN** three sessions of one subject each hold the same finding, and `devops review export-feedback --status ALL` runs
- **THEN** it prints "Appended 1 ALL finding(s)" and the dataset holds one record

### Requirement: The newest human verdict of the subject is exported
For each finding, the export SHALL use the verdict that a person gave it with the newest `verified_at` in any session of its subject. When no person judged the finding, it SHALL use the verdict of the session that review history ranks highest among the subject's sessions. The status filter SHALL apply to that verdict.

#### Scenario: Human verdicts on different findings in different sessions
- **WHEN** one session of a subject holds a person's INVALIDATED verdict on finding A, and another session holds a person's VERIFIED verdict on finding B
- **THEN** the export appends two records: A INVALIDATED and B VERIFIED, both labelled `human`

#### Scenario: Two human verdicts on one finding
- **WHEN** an older session of a subject holds a person's INVALIDATED verdict given at a later time, and a newer session holds a person's VERIFIED verdict on the same finding given at an earlier time
- **THEN** the export appends one record, INVALIDATED, from the older session

#### Scenario: An overturned verdict is not exported
- **WHEN** one session holds a person's INVALIDATED verdict on a finding, a later verdict of a person in another session of the subject is VERIFIED, and the export runs with its default status
- **THEN** it appends nothing and creates no dataset

### Requirement: A repeat of an exported subject adds nothing
The export SHALL identify a record that has a fingerprint v2 by its subject (or its session when it has no subject), its fingerprint v2, its status and its labeller, so that a later session with the same verdicts appends no record, and a person's later verdict appends one.

#### Scenario: A later session, then a person's verdict
- **WHEN** a subject's finding is exported, a later session of the subject holds the same finding with the same verdict, and a third session holds a person's VERIFIED verdict on it
- **THEN** the second export appends nothing, and the third appends one VERIFIED record labelled `human`

### Requirement: Sessions without a subject and findings without a fingerprint stay apart
A session that records no subject SHALL be exported as a subject of its own. A finding without a fingerprint v2 SHALL be matched only with its copies in its own session, never by its title or location.

#### Scenario: A target-only session and an unkeyed session
- **WHEN** a session with a profile target and no subject holds findings A and B, and a session with neither holds finding A
- **THEN** the export appends three records, each with the session id of its session and no subject key

#### Scenario: A finding without a fingerprint in two sessions of one subject
- **WHEN** two sessions of one subject each hold a finding with the same title and location and no fingerprint v2
- **THEN** the export appends one record for each session

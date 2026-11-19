## Purpose
The review reads tool and library manuals from the research index, keeps only the records at the pinned version and before their expiry, and reports each record it drops or cannot read under the source URL, the fetch date and the content hash.

## ADDED Requirements

### Requirement: A manual is returned only at the pinned version
The review manual lookup SHALL return a manual only when the version range of its research record contains the version of that component read from the lock files at read time, and SHALL list every record whose range excludes that version in the drift list with reason `version_drift`.

#### Scenario: A record inside the pinned range
- **WHEN** A research record has a version range that contains the version of its component in the lock files at read time
- **THEN** The lookup returns the manual and the drift list holds no entry for that record

#### Scenario: A record outside the pinned range
- **WHEN** A research record has a version range that excludes the version of its component in the lock files at read time
- **THEN** The lookup returns no manual and the drift list holds the record with reason version_drift

### Requirement: An expired record is not returned and is reported as expired
The review manual lookup SHALL return no manual for a research record whose expiry date is before the read time and SHALL list that record in the drift list with reason `expired`.

#### Scenario: An expired record
- **WHEN** A research record has an expiry date before the read time
- **THEN** The lookup returns no manual and the drift list holds the record with reason expired

### Requirement: A record refused at ingest is reported
The review manual lookup SHALL return no manual for a research record that the ingest refused and SHALL list that record in the drift list with reason `refused_at_ingest`.

#### Scenario: A record refused at ingest
- **WHEN** A research record carries the mark that the ingest refused it
- **THEN** The lookup returns no manual and the drift list holds the record with reason refused_at_ingest

### Requirement: The key of a returned manual names its URL, date and hash
The review SHALL name each returned manual by the key `kb:<source_url>@<fetch_date>@<sha16>`, where the date is the fetch date in ISO 8601 and the hash is the first 16 hexadecimal characters of the content hash of the record.

#### Scenario: The key of a returned manual
- **WHEN** The lookup returns a manual from a research record
- **THEN** The key of the manual is kb:<source_url>@<fetch_date>@<sha16> and the report shows that key

### Requirement: A manual index that the review cannot read is a reported gap
The review manual lookup SHALL return no manual and SHALL add one drift entry that names the setting qdrant.url when the research store is not configured, and SHALL add one drift entry with reason `index_unreachable` when the read of the store fails, so a review with no readable store still renders its report.

#### Scenario: An unset research store
- **WHEN** The review runs with the setting qdrant.url unset
- **THEN** The lookup returns no manual, the drift list holds one entry that names qdrant.url, and no request is sent

#### Scenario: An unreachable research store
- **WHEN** The research store refuses the read
- **THEN** The lookup returns no manual and the drift list holds one entry with reason index_unreachable

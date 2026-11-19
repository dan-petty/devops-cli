## MODIFIED Requirements

### Requirement: A deferred part is linked by a body line, a comment and a record
Refine SHALL NOT link a deferred part as a sub-issue of the item. After it files the parts, refine SHALL name each new issue number under `### Moved to new items` in its section, SHALL post one event comment that names that part and no issue number, and SHALL record the numbers, comma separated, as `refine.deferred` in the job record.

#### Scenario: The links of two parts
- **WHEN** refine files two parts of item 7 as issues 21 and 22
- **THEN** the refine section of item 7 holds `### Moved to new items` with `#21, #22`, its one refine comment names neither number, the job record of item 7 holds `refine.deferred` `21,22` and the hash of the new section, and item 7 has no sub-issue

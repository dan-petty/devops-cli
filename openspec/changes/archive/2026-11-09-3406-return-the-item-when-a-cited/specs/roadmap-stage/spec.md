## ADDED Requirements

### Requirement: A cited class field is probed at the staging commit
The premise probe SHALL read a cited `Class.field` reference as a class field when the staging
commit defines the class, and SHALL name the file and line of the field when the class defines it.

#### Scenario: A class that defines the cited field
- **WHEN** The issue body cites `PullStatus.labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The probe text says that `PullStatus` defines `labels` at its file and line, and the reference is not in the probe's missing list

#### Scenario: A class without the cited field
- **WHEN** The issue body cites `PullStatus.unknown_field` and `PullStatus` at the staging commit defines no `unknown_field`
- **THEN** The probe text says that `PullStatus` defines no `unknown_field`, and the reference is in the probe's missing list

#### Scenario: The cited dotted reference names a class
- **WHEN** The issue body cites `PullStatus.labels` and the staging commit defines the class `PullStatus`
- **THEN** The probe text holds no line that says the path `PullStatus.labels` is no file of the staging commit

### Requirement: A false absence returns the item
The stage job SHALL return an item to New with the probe evidence when the issue body states that a
cited class field is absent and the staging commit defines it, and SHALL make no model call for the
item.

#### Scenario: The body says a field is absent while the class defines it
- **WHEN** The body says that `PullStatus` defines no `labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The stage job returns the item to New, and its comment quotes the probe line that names the file and line of `labels`

#### Scenario: The item waits on a body edit
- **WHEN** The body states that a cited class field is absent and the staging commit defines it
- **THEN** The stage job records `refine.next_step` as `edit` for the item

### Requirement: Bounded read-only field probe
The field probe MUST count each git command against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` and
MUST leave the checkout unchanged.

#### Scenario: A probe of cited fields
- **WHEN** The probe reads a cited class field at the staging commit
- **THEN** The probe reports its command count against `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS`, and `git status --porcelain` of the checkout stays empty

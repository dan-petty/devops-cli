## ADDED Requirements

### Requirement: A finding type in a plan is a member of DefectType
The stage job SHALL refuse a plan whose free text names a verification finding type that is not a member of `DefectType`.

#### Scenario: Unknown verification kind
- **WHEN** A plan names `kind: placeholder` for a verification classification, and `placeholder` is not a member of `DefectType`.
- **THEN** `content_problems` returns a problem that names `placeholder` and lists the members of `DefectType`.

#### Scenario: Known finding kind
- **WHEN** A plan says a finding has `kind: other`, and `other` is a member of `DefectType`.
- **THEN** `content_problems` returns no problem for the finding-type rule.

#### Scenario: Mapped classification
- **WHEN** A plan maps an unlisted classification to `DefectType.OTHER`.
- **THEN** `content_problems` returns no problem for the finding-type rule.

#### Scenario: Unknown qualified type
- **WHEN** A plan names a `DefectType.` member that is not in the enum.
- **THEN** `content_problems` returns a problem that names the member and lists the members of `DefectType`.

#### Scenario: Group kind other
- **WHEN** A task group has `kind: other`, and no finding or defect sentence in the plan names a type.
- **THEN** `content_problems` returns no problem for the finding-type rule.

#### Scenario: A path is no finding type
- **WHEN** A plan names the path `src/devops_cli/roadmap/stage_verify.py` in `reads` or `changes`, and no finding sentence names a type.
- **THEN** `content_problems` returns no problem for the finding-type rule.

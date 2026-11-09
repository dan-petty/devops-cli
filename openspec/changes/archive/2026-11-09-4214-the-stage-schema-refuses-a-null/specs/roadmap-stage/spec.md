## ADDED Requirements

### Requirement: A reference reason may be null
The schema of a reference in the reply of the stage job SHALL accept `null` or a string as `reason`. A reference with `unchanged` true SHALL have a reason that is a non-blank string, and the schema SHALL refuse `null` there. The prompt of the stage job SHALL give `reason` the value that the schema accepts when `unchanged` is false.

#### Scenario: A changed reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` false and `reason` null
- **THEN** the reply passes the schema

#### Scenario: An unchanged reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` true and `reason` null
- **THEN** the schema refuses the reply and names the path of the reference

#### Scenario: A reply built from the prompt
- **WHEN** a reply holds a reference with `unchanged` false and the `reason` that the prompt states for that case
- **THEN** the reply passes the schema

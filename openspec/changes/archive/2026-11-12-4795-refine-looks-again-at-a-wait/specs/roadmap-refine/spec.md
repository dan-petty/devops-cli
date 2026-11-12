## ADDED Requirements

### Requirement: A person wait that older rules set gets one new look
A round that writes a proposal SHALL record `CONST_ROADMAP_REFINE_RULES_SINCE` as `refine.rules`. A round SHALL refine an unchanged item that waits on a person when its `refine.rules` is older than that constant, or, when the record holds none, when refine's last comment is older. A wait on a person that the current rules set SHALL stay.

#### Scenario: A wait from before the rules
- **WHEN** an item waits on a person since a refine comment older than the rules, its record holds no version, and its body is unchanged
- **THEN** the next round refines it and records the current version, and a round after it that gets the same question again makes no model call

#### Scenario: A wait with the current version
- **WHEN** an item waits on a person, and its record holds the current version while refine's comment is older than the rules
- **THEN** the next round leaves it waiting on a person and makes no model call

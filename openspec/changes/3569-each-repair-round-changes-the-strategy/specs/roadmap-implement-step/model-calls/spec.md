## ADDED Requirements

### Requirement: The third attempt moves to the next tier
The third attempt of a step MUST run on the next healthy tier of `roadmap.implement.ladder` for its class when the ladder holds more than one tier. The step SHALL discard the checkout back to its last kept commit and SHALL send the repair message, which holds the reason of the failed attempt, in a new conversation. The move SHALL spend no repair round, and the attempt SHALL happen only while a repair round is left. Each later attempt SHALL run on that tier and SHALL spend a round.

#### Scenario: A ladder of two tiers
- **WHEN** the ladder of the class names two tiers and the first two attempts fail with a repairable class
- **THEN** the third attempt calls the model of the second tier, its message holds the reason of the second attempt, and its attempt event names that tier and the strategy tier

#### Scenario: A ladder of one tier
- **WHEN** the ladder of the class names one tier and the second attempt fails with a repairable class
- **THEN** the third attempt runs on that tier, spends no repair round, and its attempt event names the strategy tier

### Requirement: A stop on a ladder of one tier names the setting
A stop whose failure selects the action `change_tier` on a ladder of exactly one tier MUST name `roadmap.implement.ladder` and the tier of that ladder in its reason.

#### Scenario: A parser failure on a ladder of one tier
- **WHEN** the ladder of the class names one tier and a failure selects the action change_tier
- **THEN** the reason of the stopped step names the setting roadmap.implement.ladder and the name of that tier

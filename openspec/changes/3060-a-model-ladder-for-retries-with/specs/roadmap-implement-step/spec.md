## ADDED Requirements

### Requirement: The step chooses a tier per attempt from the ladder
The implement step SHALL choose the model tier of each attempt from the ladder setting of its step class.

#### Scenario: The first attempt uses the first tier
- **WHEN** a step starts and the ladder of its class lists tier 1 then tier 2
- **THEN** the first attempt uses tier 1

#### Scenario: A provider error moves to the next tier
- **WHEN** an attempt fails with a provider error
- **THEN** the next attempt uses the next tier of the ladder and the repair round counter does not change

#### Scenario: An unhealthy tier is skipped
- **WHEN** the gateway reports the next tier unhealthy
- **THEN** the step skips that tier and uses the next healthy tier

#### Scenario: A ladder of local tiers sends no hosted request
- **WHEN** the ladder names only local tiers and a step runs
- **THEN** no request goes to a hosted provider

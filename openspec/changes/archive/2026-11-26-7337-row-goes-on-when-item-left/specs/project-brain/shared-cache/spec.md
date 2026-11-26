## ADDED Requirements

### Requirement: A delivery that says that an issue left removes its entry
For a delivery `issues` with the action `transferred` or `deleted`, the roadmap consumer of the webhook route SHALL remove the brain entry of the issue of the delivery before it wakes the lanes, and SHALL write no entry from the payload of the delivery. The trigger of the delivery SHALL name the number of the issue as its subject. For such a delivery whose sender is the bot of the App, the route SHALL remove the entry, SHALL write none and SHALL wake no lane.

#### Scenario: A transferred issue and a deleted issue
- **WHEN** a signed delivery `issues` with the action `labeled` wrote the entry of issue 42 of a public repository, and a signed delivery `issues` with the action `transferred`, or with the action `deleted`, comes for issue 42
- **THEN** the route answers 202, the shared tier holds no entry of issue 42 when the lanes wake and after, and the trigger of the delivery names the event `issues`, the action and the subject 42

#### Scenario: A delivery of the App itself
- **WHEN** a signed delivery `issues` with the action `transferred`, or with the action `deleted`, whose sender is the bot of the App comes for issue 42, one time while the shared tier holds no entry of issue 42 and one time while it holds one
- **THEN** the route answers 200 each time, the shared tier holds no entry of issue 42 after each delivery, and no trigger is queued

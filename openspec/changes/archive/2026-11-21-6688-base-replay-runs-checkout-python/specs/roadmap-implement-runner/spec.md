## ADDED Requirements

### Requirement: The base replay of a step runs the pytest of the checkout
The base replay of a behavior group SHALL run the pytest of `<checkout>/.venv/bin/python`. The replay names its interpreter and does not read PATH, and the image venv holds no pytest.

#### Scenario: The base replay of a behavior group
- **WHEN** a step replays the test files of a behavior group on its base commit
- **THEN** the replay starts `<checkout>/.venv/bin/python -m pytest`

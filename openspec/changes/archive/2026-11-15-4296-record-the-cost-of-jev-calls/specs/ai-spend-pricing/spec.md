## ADDED Requirements

### Requirement: A Jev decision call is recorded in the spend ledger
Each Jev decision call SHALL add one row to the spend ledger with the model `typesafe/jev-1.14`, the prompt and output tokens of the answer, and the cost of those tokens at the Jev price of 0.042 USD per million input tokens with no output charge. The call SHALL record the row after it gets the answer, in `decide_with_jev` and in the decision of `roadmap intake`.

#### Scenario: One call through the Jev fake
- **WHEN** one decision call runs against `JevFake`, which answers 64 input tokens
- **THEN** the ledger holds one row for `typesafe/jev-1.14` with 64 prompt tokens and a cost that is the price of those tokens

#### Scenario: A cost report after one call
- **WHEN** one Jev call is recorded and `devops ai cost report --by model` runs
- **THEN** the report lists `typesafe/jev-1.14` with a non-zero token count

### Requirement: The Jev price is a built-in default
The pricing registry SHALL hold the Jev price in its built-in prices, so a call is priced with no setting and no file. `ai.price_overrides` and the file of `set-price` SHALL win over it, and the Service ConfigMap SHALL set the same rates.

#### Scenario: A workstation with no setting prices a Jev call
- **WHEN** the registry builds with no `ai.price_overrides` and no price file
- **THEN** it prices one million input tokens of `typesafe/jev-1.14` at 0.042 USD

### Requirement: A failed spend record leaves the Jev answer
A Jev call MUST return its answer when the spend record cannot be written or the answer names no usage.

#### Scenario: The ledger write fails
- **WHEN** the ledger raises during the record of a Jev call
- **THEN** the call returns its typed answer and the caller sees no exception

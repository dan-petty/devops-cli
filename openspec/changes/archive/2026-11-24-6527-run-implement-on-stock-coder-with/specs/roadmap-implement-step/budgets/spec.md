## ADDED Requirements

### Requirement: Each limit that ends an implement step is a setting
The implement step SHALL read each limit that ends its run from `roadmap.implement` when the step starts. The default of each new setting SHALL be the value of the constant that it replaces, so a step with no configuration does not change. The file tools of the harness SHALL take the tool retries in place of their own count. The settings SHALL hold no limit on refused commands.

#### Scenario: No configuration
- **WHEN** no source sets the request limit, the tool-call limit, the tool retries or the extension window
- **THEN** the request limit, the tool-call limit, the tool retries and the extension window are 500, 1500, 5 and 20, the values of the constants that they replace

#### Scenario: The retry limit of a setting
- **WHEN** the tool retries are 2
- **THEN** a third call of a file tool in a row with no path argument stops a step

#### Scenario: No resend and a small request limit
- **WHEN** the resends are 0 and the request limit is 2
- **THEN** a request that fails with a 400 inside a stream is not sent again, and a model that reads in every reply gets 2 requests

#### Scenario: The window of the extension
- **WHEN** the extension window is 10
- **THEN** the digest of the tool log counts the last 10 calls, and a step at its token budget with a successful edit in them gets the extension

### Requirement: An implement limit has a ceiling
The settings load SHALL refuse a value of an implement limit above `CONST_ROADMAP_LIMIT_CEILING_FACTOR` times its default, with an error that names the setting.

#### Scenario: A value above the ceiling
- **WHEN** the request limit of an implement step is above that ceiling
- **THEN** the settings load fails with an error that names the setting of the request limit

### Requirement: The implement settings hold no refusal count
The settings of `roadmap.implement` SHALL hold no max_refusals, no max_consecutive_refusals and no extension_max_refused, and the settings load SHALL ignore a key that names one.

#### Scenario: A configuration names a refusal count
- **WHEN** a configuration sets a total of refusals, a count of refusals in a row and a refused window of the extension
- **THEN** the settings load, and the settings hold none of the three names

## MODIFIED Requirements

### Requirement: The digest of progress holds counts of the tool log
The digest SHALL count, in the last `roadmap.implement.extension_calls` tool calls of the step (default 20) over all its turns and tiers, the successful edits, which are a write_file or an edit_file call with the outcome ok. A log with fewer tool calls than that SHALL give no digest. The digest SHALL hold counts only.

#### Scenario: The counts of the last calls
- **WHEN** the log holds 21 calls: an edit_file with the outcome ok, 17 reads, a write_file with the outcome ok, an edit_file with the outcome retry and a write_file that failed
- **THEN** the digest holds 20 calls and 1 successful edit, because the first edit is out of the window

#### Scenario: A short log
- **WHEN** the log holds 19 calls
- **THEN** the log gives no digest

### Requirement: A step that makes progress gets one extension of its token budget
When a step reaches `roadmap.implement.step_token_budget` and no other budget is spent, the step SHALL read the digest of its last `extension_calls` tool calls (default 20) in its tool log. With at least 1 successful edit, the step SHALL raise its token budget one time by 50 percent, up to `step_token_ceiling`, and go on. The rule is the only resolver of the decision point `implement.extension`, and no decision model takes part.

#### Scenario: The shapes of pilot 3 that a person finished
- **WHEN** a step reaches a budget of 50 tokens with the successful edits of one of the 16 stops of pilot 3 that a person finished later, from 1 to 10 in its last 20 tool calls
- **THEN** the budget is not spent, and the extension holds a budget of 75 tokens and that count

#### Scenario: The ceiling cuts the extension
- **WHEN** the step budget is 50 tokens, the ceiling is 60 tokens and the step makes progress at its budget
- **THEN** the extension holds a budget of 60 tokens and says that the ceiling cut it

### Requirement: A step with no progress at its token budget stops as before
The step SHALL stop with the class limit_reached at its token budget, and SHALL name the step token budget and its value, when its tool log gives no digest, when the digest holds no successful edit, when the ceiling leaves no room above the tokens already used, or when the step already used its extension. A step SHALL decide one time at each limit.

#### Scenario: The shapes of pilot 3 that repeated refused commands
- **WHEN** a step reaches a budget of 50 tokens with no successful edit in its last 20 tool calls
- **THEN** the step stops, and the reason names the step token budget of 50 and that its last 20 tool calls hold no successful edit

#### Scenario: A step that repeats refused commands
- **WHEN** the step budget is 50 tokens and the first reply makes 20 tool calls with no edit
- **THEN** the model gets no second request, the step stops with the class limit_reached, and the outcome holds no extension

#### Scenario: The item budget holds
- **WHEN** a step got its extension and then reaches the item token budget before the end of the extension
- **THEN** the step stops with the class limit_reached, and the reason names the item token budget

### Requirement: The reason of a stop at the token budget names its cause
The reason of a stop at the token budget SHALL give the count of the digest, say that the log holds fewer tool calls than the extension window (default 20), name the ceiling and its value, or name the new budget of the extension.

#### Scenario: A short log at the budget
- **WHEN** a step reaches its budget after 3 tool calls
- **THEN** the step stops with the class limit_reached, and the reason says that the log holds fewer than 20 tool calls

#### Scenario: The second limit
- **WHEN** an extended step reaches its new budget of 75 tokens
- **THEN** the step stops with the class limit_reached, and the reason names the step budget of 50 tokens and the extension to 75 new tokens

#### Scenario: The ceiling ends the extension
- **WHEN** the ceiling of 60 tokens cut the extension and the step reaches 60 tokens
- **THEN** the step stops, and the reason names the ceiling of 60 tokens

#### Scenario: The ceiling leaves no room
- **WHEN** the ceiling is equal to the step budget and the step makes progress at its budget
- **THEN** the step stops, and the reason names the ceiling and its value

### Requirement: The Job log and the outcome show the extension
The step SHALL write one line to the Job log that names the rule `implement.extension`, the old and the new budget, and the count. The outcome of the step SHALL hold the extension: the old budget, the new budget, the count and whether the ceiling cut it.

#### Scenario: A step that edits at its budget
- **WHEN** the step budget is 250 tokens and the first reply makes 20 tool calls with 3 successful edits and counts 280 new tokens
- **THEN** the model gets a second request, the step ends done, and the Job log names the extension from 250 to 375 new tokens with 3 successful edits

## REMOVED Requirements

### Requirement: The limits that end an implement step are settings
**Reason**: Its text and two of its scenarios name the refusal settings and the refused window of the extension, which the step no longer holds, and a modified block cannot omit a base scenario.
**Migration**: Each limit that ends an implement step is a setting

### Requirement: An implement limit has a ceiling and an order
**Reason**: Its text and one scenario state the order of the refusal settings, which the settings no longer hold.
**Migration**: An implement limit has a ceiling

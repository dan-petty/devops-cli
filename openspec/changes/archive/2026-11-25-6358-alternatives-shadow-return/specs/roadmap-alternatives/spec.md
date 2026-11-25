## MODIFIED Requirements

### Requirement: Shadow mode records the band only
The `alternatives.reply_fixable` decision point SHALL run in mode `shadow` and record its band with no change to the job behavior.

#### Scenario: Shadow records a band and keeps the 3-day wait
- **WHEN** the mode of `alternatives.reply_fixable` is `shadow` and the reply is a fixable refusal
- **THEN** the result line holds the band `review` and the job makes no second model call and sets the next try 3 days later

#### Scenario: Shadow keeps the off-path return on a repeated fixable code
- **WHEN** `alternatives.reply_fixable` runs in mode `shadow` with `earlier_code` equal to `job_verdict`, `no_search`, or `skip_only`
- **THEN** the job executes the one return as in mode `off`, records `band` as `continue` when the second reply is also refused, and in mode `on` executes zero returns

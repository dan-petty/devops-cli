## ADDED Requirements

### Requirement: A Jev screen may skip the model review of a plan
With `roadmap.stage.jev_screen` set to `on`, the stage job SHALL ask Jev nine yes/no questions about a digest of the input of the review before the review, and SHALL skip the review when no probability reaches its fitted cut. Any other band SHALL run the review. With `shadow`, the stage job SHALL ask Jev, log and count the band, and SHALL run the review. With `off`, the default, the stage job SHALL make no Jev request.

#### Scenario: The setting is off
- **WHEN** the stage job reviews a plan and `roadmap.stage.jev_screen` is `off`
- **THEN** the reviewer runs and no request goes to Jev

#### Scenario: Mode on and the band continue
- **WHEN** the setting is `on` and every probability is under its cut
- **THEN** the reviewer is not called and the plan has no finding

#### Scenario: Mode on and a probability at its cut
- **WHEN** the setting is `on` and one probability is at or above its cut
- **THEN** the reviewer runs

#### Scenario: Mode shadow
- **WHEN** the setting is `shadow`
- **THEN** the reviewer runs, one counter point names the band, and one point names the band and the result of the reviewer

### Requirement: The screen fails open
The screen SHALL run the review when the request to Jev raises an error, times out or leaves a question unanswered. It SHALL log the error and count `error`.

#### Scenario: Jev fails
- **WHEN** the setting is `on` and the request to Jev fails with HTTP 503
- **THEN** the reviewer runs, one warning names the error, and the counter counts `error`

### Requirement: The cuts of the screen are fitted data
The cuts of the screen SHALL be read from `jev_screen_cuts.json`, which SHALL hold the Jev model, the day of the fit, the number of cases and the numbers of the check on the other half. The file SHALL have a cut for each question of the screen.

#### Scenario: The data file
- **WHEN** a test loads the cuts of the screen
- **THEN** each of the nine questions has a cut, and the file names the model and the cases of its fit

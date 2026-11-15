## ADDED Requirements

### Requirement: A prompt change waits for its live eval scores
`draft_readiness` SHALL refuse a draft whose changed files hold `src/devops_cli/ai/tasks/roadmap_stage_change.md` and whose body holds no number on the last `Base eval score:` line or the last `Head eval score:` line. The reason SHALL name each missing marker. The rule SHALL NOT apply to a draft whose files hold no such path. `read_draft` SHALL pass the compare files of every kind to the draft, and the ready step of the implement job SHALL pass the paths of its local diff.

#### Scenario: A prompt change with no score
- **WHEN** the function reads a complete draft that changes the stage prompt and its body holds no score line
- **THEN** it answers refuse, and the reason names the base score and the head score

#### Scenario: A prompt change with one score
- **WHEN** the body holds a base score and no head score, or a head score and no base score
- **THEN** it answers refuse, and the reason names only the missing score

#### Scenario: A prompt change with both scores
- **WHEN** the body holds `Base eval score: 11` and `Head eval score: 12`
- **THEN** it answers ready

#### Scenario: A repeated marker and a marker with no number
- **WHEN** the body holds two base score lines whose last line has a number, and a head score line with no number
- **THEN** it answers refuse, and the reason names the head score only

#### Scenario: A change without the prompt file
- **WHEN** the changed files hold no stage prompt path and the body holds no score
- **THEN** the score rule answers no reason, and the other rules decide

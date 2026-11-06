## MODIFIED Requirements

### Requirement: The comment gives the verdict and its evidence
The comment SHALL give the verdict, the reason of the verdict in the model's words, the tool with its license, its last activity, whether it is maintained and its URL, what it covers and lacks, every tool whose facts the run read with its URL, license and last activity, and the searches run, each with its number of results. It SHALL show at most five sources, and SHALL say how many more it leaves out. The model SHALL give a reason in every reply, and the job SHALL refuse a reply with none. A check SHALL add a new comment and SHALL NOT change the comment of an earlier check.

#### Scenario: A comment
- **WHEN** a check ends with a covering tool
- **THEN** the comment names the verdict, the reason, the tool, its license, its last push, its maintained state, its URL, the lists of covers and lacks, the tools considered, and the queries run

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the comment lists each query with `results: 2`

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the comment lists both under `Tools considered:`, each with its license and last activity

#### Scenario: More sources than the bound
- **WHEN** the reply cites eight sources that the tools returned
- **THEN** the comment shows five and the line `3 more sources are left out`

#### Scenario: A reply with no reason
- **WHEN** the model replies with no reason
- **THEN** the reply fails the schema of the output and the model is asked again

#### Scenario: A later check
- **WHEN** a second check of the same item writes its comment
- **THEN** the item has two comments and the first is unchanged

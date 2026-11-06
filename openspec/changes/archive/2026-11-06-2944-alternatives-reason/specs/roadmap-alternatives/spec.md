## MODIFIED Requirements

### Requirement: The comment gives the verdict and its evidence
The comment SHALL give the verdict, the reason of the verdict in the model's words, the tool with its license, its last activity, whether it is maintained and its URL, and what it covers and lacks. The model SHALL give a reason in every reply, and the job SHALL refuse a reply with none.

#### Scenario: A comment
- **WHEN** a check ends with a covering tool
- **THEN** the comment names the verdict, the reason, the tool, its license, its last push, its maintained state, its URL, the lists of covers and lacks, the tools considered, and the queries run

#### Scenario: A reply with no reason
- **WHEN** the model replies with no reason
- **THEN** the reply fails the schema of the output and the model is asked again


## ADDED Requirements

### Requirement: The comment lists the searches and the tools considered
The comment SHALL list every tool whose facts the run read with its URL, license and last activity, and each search that ran with its number of results.

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the comment lists each query with `results: 2`

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the comment lists both under `Tools considered:`, each with its license and last activity

### Requirement: The comment shows at most five sources
The comment SHALL show at most five sources, and SHALL say how many more it leaves out.

#### Scenario: More sources than the bound
- **WHEN** the reply cites eight sources that the tools returned
- **THEN** the comment shows five and the line `3 more sources are left out`

### Requirement: A check never changes an earlier comment
A check SHALL add a new comment and SHALL NOT change the comment of an earlier check.

#### Scenario: A later check
- **WHEN** a second check of the same item writes its comment
- **THEN** the item has two comments and the first is unchanged

## MODIFIED Requirements

### Requirement: The comment gives the verdict and its evidence
The comment SHALL give the verdict, the reason of the verdict in the model's words, the tool on one line with its URL, its license, its last activity and whether it is maintained, and what it covers and lacks. The model SHALL give a reason in every reply, and the job SHALL refuse a reply with none. The prompt SHALL ask for a brief reply, and the job SHALL refuse no reply for its length and SHALL cut no text of it.

#### Scenario: A comment
- **WHEN** a check ends with a covering tool
- **THEN** the comment names the verdict, the reason, the tool, its URL, its license, its last push and its maintained state on one line, the lists of covers and lacks, and, in a folded block, the tools considered and the queries run

#### Scenario: A reply with no reason
- **WHEN** the model replies with no reason
- **THEN** the reply fails the schema of the output and the model is asked again

#### Scenario: A reply longer than the prompt asks
- **WHEN** the model replies with a reason of six sentences and five long items in `lacks`
- **THEN** the model gets no request to write the reply again, and the comment holds the whole reason and each item

### Requirement: The comment lists the searches and the tools considered
The comment SHALL list every tool whose facts the run read with its URL, license and last activity, and each search that a provider answered with its number of results. It SHALL put them, with the sources, in one `<details>` block whose summary is `Searches (<count>)`, so GitHub shows them closed. It SHALL show no query outside that block.

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the folded block `Searches (2)` lists each query with `results: 2`, and no query is outside the block

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the folded block lists both under `Tools considered:`, each with its license and last activity

#### Scenario: Ten searches
- **WHEN** a run makes ten searches and names a covering tool with three covers and three lacks
- **THEN** the comment outside the folded block holds only the marker, the heading, the reason, the tool line, the covers, the lacks and the footer, and the block `Searches (10)` lists the ten queries

### Requirement: The comment shows at most five sources
The folded block of the comment SHALL show at most five sources, and SHALL say how many more it leaves out.

#### Scenario: More sources than the bound
- **WHEN** the reply cites eight sources that the tools returned
- **THEN** the folded block shows five and the line `3 more sources are left out`

### Requirement: A skip-class item is not-applicable with no model call
The check SHALL give the verdict `not-applicable`, with no model call and no search, to an item whose title has the Conventional Commit type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and to an item whose title has the type `fix` and whose body holds the text `Traceback (most recent call last)`. The comment and the block of the body SHALL name the class: the type, or `fix-with-stack-trace`. An item of any other type, and an item with no type, SHALL NOT be a skip class.

#### Scenario: Each type is a skip class
- **WHEN** the check runs on six items whose titles have the types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`
- **THEN** each check has the verdict `not-applicable`, each comment is the one line that names the type, and the model received no request and no search ran

#### Scenario: The base rule of one agent run holds for non-skip items only
- **WHEN** the check runs on a skip-class item
- **THEN** no agent run happens for it, and the rule "The check of one item SHALL be one agent run" of the requirement "The agent finds facts with three tools only" holds for an item that is not a skip class

#### Scenario: A fix with a stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds `Traceback (most recent call last)`
- **THEN** the check has the verdict `not-applicable`, the comment is the one line that names `fix-with-stack-trace`, and the model received no request

#### Scenario: A fix with no stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds no traceback
- **THEN** the model receives a request for the item

#### Scenario: A type that is no skip class
- **WHEN** the check runs on items whose titles have the types `feat`, `build` and `style`, and on an item whose title has no type
- **THEN** the model receives a request for each of them

#### Scenario: A skip class with an unpaired marker
- **WHEN** the body of a skip-class item holds the start marker of the block with no end marker
- **THEN** the item is skipped with a named reason and nothing is written for it

## ADDED Requirements

### Requirement: The comment of a skip class is one line
The comment of a skip-class item SHALL be the marker and one line, `Alternatives check: not-applicable (<class> item; no search).`

#### Scenario: A docs item
- **WHEN** the check runs on an item titled `docs(roadmap): a change`
- **THEN** its comment is the marker and the line `Alternatives check: not-applicable (docs item; no search).`

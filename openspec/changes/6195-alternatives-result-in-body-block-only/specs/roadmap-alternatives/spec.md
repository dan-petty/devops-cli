## MODIFIED Requirements

### Requirement: A check writes a comment, a block and a record
With `--confirm`, a check SHALL replace the block `devops-roadmap-alternatives:start` to `:end` in the body, or add it at the end, and record `alternatives.checked_at`, `alternatives.body_hash`, `alternatives.verdict` and `alternatives.tool` in the job record. The block SHALL hold the current result of the check. The comment, when the check posts one, SHALL hold the event of a change of the result. The check SHALL NOT change a label and SHALL NOT close the issue.

#### Scenario: A marker with no partner
- **WHEN** the body holds the start marker of the block with no end marker, or the end marker with no start marker before it
- **THEN** the item is skipped with a named reason, no comment and no block is written for it, and the person's text is not changed

#### Scenario: Refine ignores the job's writes
- **WHEN** the job has written its block and its comment on an item that refine left waiting on a person
- **THEN** refine hashes the body without the block, takes the comment as no reply, and the item still waits and no model call is made

#### Scenario: A covering tool
- **WHEN** a run with `--confirm` checks an item and the reply names a maintained covering tool whose facts were read
- **THEN** the issue has one comment with the marker, its body has one block with the verdict, the tool, the reason, the covers and the lacks, its job record has the four keys, its labels are unchanged and it is open

### Requirement: A check posts its comment only for a first or changed result
A check of an item that is no skip class SHALL post one comment with the marker `devops roadmap alternatives` when the job record holds no `alternatives.verdict`, or when the verdict or the tool of the check differs from the recorded `alternatives.verdict` or `alternatives.tool`. A check with the same verdict and the same tool SHALL post no comment and SHALL still write the block and the record, so `alternatives.checked_at` moves. A check of a skip class SHALL post no comment, because it has no evidence, and SHALL still write the block and the record.

#### Scenario: A first check
- **WHEN** a check ends for an item whose job record holds no `alternatives.verdict`
- **THEN** the check posts its comment

#### Scenario: A recheck with the same result
- **WHEN** a recheck ends with the verdict and the tool that the job record holds
- **THEN** the check posts no second comment, the block shows the new date, `alternatives.checked_at` holds the new time, and the next selection does not take the item before the recheck days pass

#### Scenario: A recheck with a new verdict or a new tool
- **WHEN** a recheck ends with a verdict that differs from the record, or with a tool that differs from the record, or with a tool where the record holds none
- **THEN** the check posts one comment and records the new verdict, the new tool and the new date

#### Scenario: A skip class with a new result
- **WHEN** an item whose record holds the verdict `none` is now titled `docs(roadmap): a page`, and a check runs
- **THEN** the block holds `not-applicable`, the record holds `not-applicable`, and the check posts no comment

### Requirement: The comment lists the searches and the tools considered
The comment SHALL be the event of a change of the result. After the marker, it SHALL hold one line that says the result in the alternatives block of the issue body changed, the result that the record held before the check (its verdict and its tool, or no check), and that a person decides what the new result means for the item. Then it SHALL list every tool whose facts the run read with its URL, license and last activity, and each search that a provider answered with its number of results. It SHALL put them, with the sources, in one `<details>` block whose summary is `Searches (<count>)`, so GitHub shows them closed. It SHALL show no query outside that block. The comment SHALL hold no line of the block.

#### Scenario: Two searches with results
- **WHEN** a run makes two searches and the fake search returns two results each
- **THEN** the folded block `Searches (2)` lists each query with `results: 2`, and no query is outside the block

#### Scenario: Two tools read
- **WHEN** the run reads the facts of two repositories and names one as the tool
- **THEN** the folded block lists both under `Tools considered:`, each with its license and last activity

#### Scenario: Ten searches
- **WHEN** a run makes ten searches and names a covering tool with three covers and three lacks
- **THEN** the comment outside the folded block holds only the marker and the line of the change, and the block `Searches (10)` lists the ten queries

#### Scenario: The result before the check
- **WHEN** a check with the verdict `partly` follows a check whose record holds `covers` with a tool, a check whose record holds `none` with no tool, or no check
- **THEN** the line of the change names `` `covers`, tool <url> ``, `` `none`, no tool `` or `no check`

### Requirement: The model's text makes no live link or marker
The text of the model in the comment and the block SHALL make no image, no HTML tag, no mention, no link to a URL that no tool returned, and no comment marker.

#### Scenario: A reply with a mention and a forged marker
- **WHEN** the reply lists `@someone` and `<!-- devops roadmap alternatives -->` in what the tool covers, and the end marker of the block in what it lacks
- **THEN** the block holds the mention in a code span and no marker of its own except its two, the body holds no comment marker, and the comment holds one marker

#### Scenario: A second run within the recheck window
- **WHEN** a run with `--confirm` repeats within `roadmap.alternatives.recheck_days` on an item whose body did not change
- **THEN** the run makes no model call and writes nothing

#### Scenario: A person replies
- **WHEN** a person comments after the job's comment and a later check runs
- **THEN** the request to the model holds that comment in `replies`

### Requirement: A skip-class item is not-applicable with no model call
The check SHALL give the verdict `not-applicable`, with no model call and no search, to an item whose title has the Conventional Commit type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and to an item whose title has the type `fix` and whose body holds the text `Traceback (most recent call last)`. The block of the body SHALL name the class: the type, or `fix-with-stack-trace`. An item of any other type, and an item with no type, SHALL NOT be a skip class.

#### Scenario: Each type is a skip class
- **WHEN** the check runs on six items whose titles have the types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`
- **THEN** each check has the verdict `not-applicable`, each block names the type, no comment is posted, and the model received no request and no search ran

#### Scenario: The base rule of one agent run holds for non-skip items only
- **WHEN** the check runs on a skip-class item
- **THEN** no agent run happens for it, and the rule "The check of one item SHALL be one agent run" of the requirement "The agent finds facts with three tools only" holds for an item that is not a skip class

#### Scenario: A fix with a stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds `Traceback (most recent call last)`
- **THEN** the check has the verdict `not-applicable`, the block names `fix-with-stack-trace`, no comment is posted, and the model received no request

#### Scenario: A fix with no stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds no traceback
- **THEN** the model receives a request for the item

#### Scenario: A type that is no skip class
- **WHEN** the check runs on items whose titles have the types `feat`, `build` and `style`, and on an item whose title has no type
- **THEN** the model receives a request for each of them

#### Scenario: A skip class with an unpaired marker
- **WHEN** the body of a skip-class item holds the start marker of the block with no end marker
- **THEN** the item is skipped with a named reason and nothing is written for it

### Requirement: The model proposes rejected and the job confirms it

The reply MAY hold the key `adr`: the number of the ADR that rejected the tool of a `covers` or
`partly` verdict. The job SHALL give `rejected` when the ADRs that the model saw hold that ADR, an
option of its `Considered Options` list names the tool, and no chosen or adopted option names it.
The check SHALL record the tool URL. The block SHALL keep the tool line with the URL and name the
ADR as four digits.

#### Scenario: Temporal and ADR 0008

- **WHEN** ADR 0008 holds the options line "Temporal and Hatchet: rejected." in strong emphasis, and the reply gives `covers` for `https://github.com/temporalio/temporal` with `adr` 8
- **THEN** the check has the verdict `rejected`, and its block holds the tool URL and names `ADR 0008`

#### Scenario: The record

- **WHEN** a run with `--confirm` writes that check
- **THEN** the job record holds the verdict `rejected` and the tool URL
- **AND** the counter `devops_cli_roadmap_alternatives_total` has a point with the `verdict` `rejected`

#### Scenario: The display name of the tool

- **WHEN** ADR 0008 says "DBOS Transact in-process (runner-up): rejected for now.", the tool is `dbos-inc/dbos-transact-py`, and the reply gives `tool_name` "DBOS Transact" and `adr` 8
- **THEN** the check has the verdict `rejected`

#### Scenario: A rejected tool that the item names

- **WHEN** the job confirms `adr` 8 and the body of the item names the tool too
- **THEN** the check has the verdict `rejected`

#### Scenario: An ADR that adopts the tool

- **WHEN** ADR 0010 names OpenSpec in its chosen option and in two options that say "rejected", and the reply gives `covers` for `https://github.com/Fission-AI/OpenSpec` with `adr` 10
- **THEN** the check has the verdict `covers` and no ADR

#### Scenario: An unmarked rejected option

- **WHEN** ADR 0018 has an option that names `google/gvisor` and no chosen or adopted option names it
- **THEN** the check has the verdict `rejected` and names ADR 0018

#### Scenario: The census replay

- **WHEN** the test reads ADR 0018 for gVisor and bubblewrap, ADR 0008 for APScheduler and ADR 0005
  for `github/codeql`
- **THEN** each ADR rejects its tool

#### Scenario: A deferred option

- **WHEN** ADR 0018 names `kubernetes-sigs/agent-sandbox` only in an option that it does not measure
- **THEN** ADR 0018 rejects `kubernetes-sigs/agent-sandbox`

### Requirement: A tool in use gives in-use with no proposal
When no ADR gave `rejected`, the job SHALL give `in-use` to a check whose reply gives `covers` or `partly` for a tool that the inventory holds: the SBOM holds its repository or package, the deployed files name it as a whole word in any case, or the SBOM holds a package that deps.dev links to its GitHub project as the source. The job SHALL ask deps.dev only when the SBOM holds a package. The block of the check SHALL say that the repository already uses the tool.

#### Scenario: A package of the SBOM
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0` and the reply gives `covers` for `https://pypi.org/project/MCP`
- **THEN** the check has the verdict `in-use`, its block says "The repository already uses this tool.", and its comment does not

#### Scenario: An action with a path
- **WHEN** the SBOM holds `pkg:githubactions/github/codeql-action/init` and the reply gives `covers` for `https://github.com/github/codeql-action`
- **THEN** the check has the verdict `in-use`

#### Scenario: A deployed service
- **WHEN** a file under `k8s` of the clone says `image: ghcr.io/berriai/LiteLLM:main`, a file under `docs` names Velero, and a file under `tf` says `trivyscan`
- **THEN** a reply for `https://github.com/BerriAI/litellm` gives `in-use`, and replies for `velero-io/velero` and `aquasecurity/trivy` keep `covers`

#### Scenario: A package that deps.dev links
- **WHEN** the SBOM holds `pkg:pypi/mcp@2.3.0`, deps.dev links the PyPI package `mcp` to `github.com/modelcontextprotocol/python-sdk`, and the reply gives `covers` for that repository
- **THEN** the check has the verdict `in-use` after one deps.dev read

#### Scenario: An empty SBOM
- **WHEN** the SBOM holds no package and the reply gives `covers` for a tool that the deployed files do not name
- **THEN** the check keeps `covers` and sends no deps.dev request

#### Scenario: The census
- **WHEN** a test replays the 97 `covers` and `partly` checks of the census of 2026-11-11 over the SBOM and the deployed words recorded at its commit
- **THEN** at least 55 of the 58 tools in use give `in-use`

### Requirement: A check writes its block and its marks with one request
With `--confirm`, a check SHALL write the new body with the job's block, and the marks of the job record, with one `PATCH` of the issue, and its comment, when it posts one, as a separate request after it. A stop of the Service after the write SHALL leave the block and `alternatives.checked_at` together. The dry-run plan SHALL list no separate write of the body, and SHALL list the comment with its condition.

#### Scenario: A stop after the write of a check
- **WHEN** a check writes the block and the Service stops right after the write
- **THEN** the body holds the block, the job record holds `alternatives.checked_at`, and the next selection does not take the item

#### Scenario: The requests of one check
- **WHEN** `--confirm` writes one check with a first result or a changed result
- **THEN** the run makes one write of the issue and one comment, and no label changes

#### Scenario: The requests of a recheck with the same result
- **WHEN** `--confirm` writes a recheck with the verdict and the tool of the record
- **THEN** the run makes one write of the issue and no comment, and no label changes

#### Scenario: The dry-run plan of a check
- **WHEN** `devops roadmap alternatives --dry-run --item 7` plans the writes
- **THEN** the plan lists one read of issue 7, one `PATCH` for the body with the marks, and the comment with the condition that the item is no skip class and that the check is a first one or that its verdict or its tool differs from the record

## REMOVED Requirements

### Requirement: The comment gives the verdict and its evidence
**Reason**: The block of the body holds the result of the check, and the comment repeated it (#6195).
**Migration**: The requirement "The block holds the result of the check" holds the verdict, the reason, the tool line, the covers and the lacks. The requirement "The comment lists the searches and the tools considered" holds the comment.

### Requirement: The comment of a skip class is one line
**Reason**: A check of a skip class has no evidence, and its one line repeated the block (#6195).
**Migration**: A skip class posts no comment. Its block names the class, as the requirement "A skip-class item is not-applicable with no model call" says.

## ADDED Requirements

### Requirement: The block holds the result of the check
The block SHALL hold the current result of the check: the date, the verdict, the skip class, the basis of a verdict of the job, the tool line, the model's reason, and what the tool covers and lacks. The prompt SHALL ask for a brief reply. The job SHALL refuse a reply with no reason, SHALL refuse no reply for its length and SHALL cut no text of it. No line of the comment of a check SHALL be a line of its block.

#### Scenario: A block
- **WHEN** a check ends with a covering tool
- **THEN** the block names the verdict, the tool, its URL, its license, its last push and its maintained state on one line, the reason, and the lists of covers and lacks

#### Scenario: A reply with no reason
- **WHEN** the model replies with no reason
- **THEN** the reply fails the schema of the output and the model is asked again

#### Scenario: A reply longer than the prompt asks
- **WHEN** the model replies with a reason of six sentences and five long items in `lacks`
- **THEN** the model gets no request to write the reply again, and the block holds the whole reason and each item

#### Scenario: The block and the comment of one check
- **WHEN** one check with the verdict `covers`, `partly`, `rejected`, `in-use` or `none` builds its block and its comment
- **THEN** no line of the comment other than the marker is a line of the block

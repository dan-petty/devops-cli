## MODIFIED Requirements

### Requirement: A skip-class item is not-applicable with no model call
The check SHALL give the verdict `not-applicable`, with no model call and no web search, to an item whose title has the Conventional Commit type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and to a `fix` item whose body holds `Traceback (most recent call last)`. The block SHALL name the class: the type, or `fix-with-stack-trace`. The reference step of such an item SHALL send the rule queries only. An item of any other type, and an item with no type, SHALL NOT be a skip class.

#### Scenario: Each type is a skip class
- **WHEN** the check runs on six items whose titles have the types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`
- **THEN** each check has the verdict `not-applicable`, each block names the type, no comment is posted, and the model received no request and no web search ran

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

#### Scenario: A docs item sends the rule queries
- **WHEN** the check runs on an item titled `docs(roadmap): a change` whose body holds an import statement and a code span
- **THEN** the reference step sends the two rule queries, the fake model client records no call, and the verdict is `not-applicable`

## ADDED Requirements

### Requirement: Rule queries come from the item body
The reference step SHALL build its queries from the code spans, the import lines and the package names of the item body, and SHALL add at most 3 `reference_queries` from the same model reply. The step SHALL take a rule query and a query of the model in turn. A query SHALL be plain words with no colon and no quote.

#### Scenario: A body with an import line and a code span
- **WHEN** the body holds `from pydantic_ai import Agent` and the code span `pydantic-ai`, and the fake reply holds 4 `reference_queries`
- **THEN** the store receives 3 code search queries that hold `from pydantic_ai import Agent` and `pydantic-ai`, and the model receives no request after its reply

#### Scenario: A code span that names a search qualifier
- **WHEN** the body holds the code span `repo:example/closed "token"`
- **THEN** the query is `repo example/closed token`

### Requirement: The step bounds its searches, its fact reads and its time
The step SHALL send at most 3 code searches and 15 fact reads for each item, and SHALL make no generative call of its own. The step SHALL stop after 120 s, and the check SHALL still write the verdict of the item.

#### Scenario: More queries than the limit
- **WHEN** the rule queries give 5 code searches for one item
- **THEN** the store records 3 code search requests and no fourth

#### Scenario: More candidates than the fact reads
- **WHEN** 3 code searches give 15 repositories that pass each gate
- **THEN** the step sends 15 fact reads in all and keeps 3 permalinks

#### Scenario: A provider that does not answer
- **WHEN** a fake provider holds a request open past the time bound of the step
- **THEN** the step stops with no link, the check writes the verdict, and no error stops the run

### Requirement: GitHub search is the default provider
The step SHALL search code with `GET /search/code` and repositories with `GET /search/repositories`, through the paced GitHub session, at no more than 10 and 30 requests a minute. The step SHALL use these two GitHub providers only for a private repository.

#### Scenario: The provider list of a public repository
- **WHEN** the step runs on a public repository with no optional server
- **THEN** the fake GitHub session records one `/search/code` request and one `/search/repositories` request and no other request to GitHub, and the provider list holds `github-code` and `github-repository` only

#### Scenario: A private repository
- **WHEN** the provider list is built for a private repository and an optional provider is configured
- **THEN** the provider list holds the 2 GitHub providers, and the optional provider gets no connection

### Requirement: A down optional provider does not stop the check
The step SHALL drop an optional provider whose server refuses the connection at the start of a run, and the check SHALL still write the verdict of the item. An optional MCP toolset SHALL make one connection attempt.

#### Scenario: The optional server is down at start
- **WHEN** the MCP server of `roadmap.alternatives.references_mcp_url` refuses the connection at the start
- **THEN** the provider list holds the 2 GitHub providers, the check writes the verdict of the item, and the run ends with no error

#### Scenario: The optional server answers
- **WHEN** the search tool of the server gives an answer with two links to files on GitHub
- **THEN** the provider `mcp-code` gives two code hits, each with its repository and its path

### Requirement: The gates drop an unusable hit
The step SHALL keep a hit only when it is a code hit and its repository is public, not archived, not a fork, pushed within 365 days, OSI-licensed, not this repository and not linked already in the item.

#### Scenario: An archived repository
- **WHEN** a code hit names a repository whose `archived` field is true
- **THEN** the step drops the hit and reads no head commit of that repository

#### Scenario: A hit that costs no read
- **WHEN** the code hits name this repository, a repository that the item links, and a Markdown file
- **THEN** the step sends no repository search and no fact read

### Requirement: The step ranks the candidates
The step SHALL rank the candidates by the sum of the logarithm of their stars, the logarithm of their deps.dev direct dependents, the number of PyPI packages of the SBOM whose source they are, and 1 for the tests they hold.

#### Scenario: Two candidates with the same stars
- **WHEN** two candidates have the same star count and one holds tests
- **THEN** the candidate with tests ranks first

### Requirement: A permalink is verified at the head SHA
The step SHALL render each permalink with `render_permalink` and SHALL keep it only when `repository_file` answered its path at the head SHA of its repository, and SHALL keep at most 3.

#### Scenario: A path that the head SHA does not hold
- **WHEN** the fake store raises `GitHubFileNotFoundError` for the path of a candidate at the head SHA
- **THEN** the step drops that permalink and keeps the other verified ones

### Requirement: The references setting holds off, plan and on
The setting `roadmap.alternatives.references` SHALL hold `off`, `plan` or `on`, and SHALL default to `plan`. Mode `off` SHALL run no step. Mode `plan` SHALL write the verified links to the log and add the counter points only, and SHALL change no issue text and no job record. Mode `on` SHALL write at most 3 verified permalinks in the block and in the comment, and SHALL record them in `alternatives.refs` of the job record.

#### Scenario: The default setting
- **WHEN** the setting is not set
- **THEN** the loader gives `plan`, and a value outside the three is refused

#### Scenario: A plan run that verifies two permalinks
- **WHEN** the setting is `plan` and the step verifies 2 permalinks
- **THEN** the log holds the 2 permalinks, the counter has 2 points with the result `verified`, and the fake store records no write

#### Scenario: Three verified permalinks
- **WHEN** the setting is `on` and the step verifies 3 permalinks
- **THEN** the block, the comment and `alternatives.refs` hold the 3 permalinks of the form `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<a>-L<b>`

### Requirement: Official documentation comes from the allowlist
The step SHALL accept a documentation hit only when its host is on `CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS`, its URL is `https`, and one request of its page through the HTTP entry at the public egress level answers 200.

#### Scenario: A host that is not on the allowlist
- **WHEN** a documentation hit names `example.com` and the allowlist holds `docs.python.org`
- **THEN** the step drops the hit and sends no request to `example.com`

### Requirement: The reference relevance runs in shadow
The step SHALL register the decision point `brain.reference_relevance` with one Jev question, and SHALL run it in the `shadow` mode so its band changes no rank. The settings SHALL refuse the mode `on` of the point while its cuts hold no fit.

#### Scenario: A review band in shadow
- **WHEN** the fake decision model answers `review` for a candidate in shadow mode
- **THEN** the candidate keeps its fallback rank, and the decision counter has a point with the point `brain.reference_relevance` and the band `review`

### Requirement: The step counts each search by provider and result
The step SHALL add 1 to `devops_cli_brain_references_total` with the provider and the result of each search, and with the provider of each verified link and the result `verified` in mode `plan` or `linked` after the write of mode `on`.

#### Scenario: Two linked references
- **WHEN** the step verifies 2 permalinks of the GitHub code search in mode `on` and the check writes them
- **THEN** the counter has a point with the provider `github-code` and the result `linked`

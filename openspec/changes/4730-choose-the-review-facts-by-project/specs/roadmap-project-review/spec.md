## ADDED Requirements

### Requirement: A version window needs a tag that matches the tag pattern
The project review SHALL read the review tag pattern from the review table of the roadmap file of the checkout, MUST use `v*` when the table or the key is absent, and MUST refuse a version window when no tag of the repository matches the pattern, with an error that names `tag_pattern` and the pattern.

#### Scenario: A repository with no tag that matches the tag pattern
- **WHEN** A fixture checkout holds the tags `release-1.0` and `release-2.0`, and the review table names the pattern `v*`.
- **THEN** `resolve_window` raises an error whose message names `tag_pattern` and `v*`, and starts no git command.

#### Scenario: A checkout with no review table
- **WHEN** A fixture checkout holds no review table in its roadmap file and holds the tag `v1.2.3`.
- **THEN** The default pattern `v*` matches the tag `v1.2.3`, so the review accepts the version window that names it.

### Requirement: The functional change comes from the CHANGELOG without openspec
The project review SHALL record the functional change of the window from the Features and Bug Fixes sections of `CHANGELOG.md` when the catalog result holds no ok fact whose id starts with `openspec.`, and the fact MUST name `changelog` as its source.

#### Scenario: A repository without openspec
- **WHEN** A fixture checkout holds a `CHANGELOG.md` with a Features section, and the catalog result holds no ok OpenSpec fact.
- **THEN** The functional change fact holds the items of the Features section and names `changelog` as its source.

### Requirement: The functional change falls back to the commit subjects
The project review SHALL record the functional change of the window from the feat and fix subjects of its commits when `CHANGELOG.md` gives no section, and the fact MUST name `subjects` as its source.

#### Scenario: A repository with neither openspec nor changelog
- **WHEN** A fixture checkout holds no OpenSpec fact and no `CHANGELOG.md`, and its window holds a feat commit and a fix commit.
- **THEN** The functional change fact holds those two subjects and names `subjects` as its source.

### Requirement: The functional change falls back to the merged pull request titles
The project review SHALL record the functional change of the window from the titles of the merged pull requests of the `listing.merged_titles` fact when no CHANGELOG section and no feat or fix subject exists, and the fact MUST name `pull_requests` as its source.

#### Scenario: A repository with only pull request titles
- **WHEN** A fixture window holds no CHANGELOG section and no feat or fix subject, and the `listing.merged_titles` fact holds two titles.
- **THEN** The functional change fact holds the two titles and names `pull_requests` as its source.

### Requirement: The complexity rank is skipped when lizard reads no hot file
The project review SHALL rank the hotspots by churn alone and MUST record the complexity rank as skipped with a reason when the window holds hot files and lizard reads none of them, and the summary MUST show that reason.

#### Scenario: A Shell-only repository
- **WHEN** A fixture window holds only Shell hot files.
- **THEN** `complexity_fact` gives a skipped fact whose reason says that no hot file is one that lizard reads, and the hotspots keep the churn rank.

## MODIFIED Requirements

### Requirement: The review writes the facts in a fixed order with the disagreements and the read counts
The facts in `data.json` SHALL be the commits, their types, the net change and the churn with generated paths apart, the release tags, the hot files and the complexity, the functional change when the catalog result holds no ok OpenSpec fact, then each fact of the catalog in the catalog order. `data.json` SHALL also hold the disagreements, and the count of the reads of each reader kind with the seconds of the collection.

#### Scenario: The facts of a fixture catalog follow the git facts
- **WHEN** the review runs with a fixture catalog of two facts in the section `service`
- **THEN** the review data holds the git facts, then the functional change fact, then the two facts of the section `service`, and the count of the reads of each reader kind

### Requirement: A dry run of the review starts no program
`devops roadmap review run --dry-run` SHALL print the git commands, the shared reads and each catalog fact with its id, its reader kind and its rendered query, with placeholders for read values. A dry run with no window option SHALL list each repository of `service.repos` with the catalog sections and facts, the reason of each unset setting and the condition of each other fact. It SHALL start no program, send no request, open no connection and write no file.

#### Scenario: A dry run lists the git commands
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --dry-run`
- **THEN** the output lists the `git log` command of each tag and the first-parent log of `<base commit>..<head commit>`, and no program starts

#### Scenario: A dry run lists the catalog queries and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run` with fakes of GitHub, Prometheus, Loki and the processes that record each call
- **THEN** the output lists each fact id of the catalog with its rendered query, and each fake records 0 calls

#### Scenario: A dry run with no window lists each repository of service.repos
- **WHEN** a person runs `devops roadmap review run --dry-run` with no window option while `service.repos` names 7 repositories and the setting `prometheus.url` has no value, with fakes of GitHub, Prometheus, Loki and the processes that record each call
- **THEN** the output holds one block for each of the 7 repositories, with the title of each section of the catalog and the id of each fact, the reason `The setting prometheus.url has no value.` on the line of each fact of the prometheus reader, the text `the base and the head commits hold openspec/specs` on the line of each fact of the openspec reader, and each fake records 0 calls

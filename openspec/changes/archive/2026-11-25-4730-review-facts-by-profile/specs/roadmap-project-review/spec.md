## ADDED Requirements

### Requirement: A version window needs a tag that matches the tag pattern
The project review SHALL read the review tag pattern from `[review] tag_pattern` of `.devops/roadmap.toml` in the checkout, SHALL use `v*` when the file or key is absent, SHALL reject invalid patterns (`ConfigurationError`), and SHALL refuse a version window when no tag of the repository matches the pattern with an error that names `tag_pattern` and the pattern before any commit lookup.

#### Scenario: A repository with no tag that matches the tag pattern
- **WHEN** a fixture checkout holds tags that do not match the configured `[review] tag_pattern` (for example empty tags for `release-*`)
- **THEN** `resolve_window` raises `RoadmapReviewError` whose message names `tag_pattern` and the pattern, and starts no git command

#### Scenario: A checkout with no review table
- **WHEN** a fixture checkout has no `[review]` table in `.devops/roadmap.toml` and holds `v1.0.0..v1.1.1` tags
- **THEN** the default pattern `v*` matches those tags and accepts the version window

### Requirement: The functional change comes from the CHANGELOG without openspec
The project review SHALL record `functional.change` from bullet items under the `### Features` and `### Bug Fixes` headings of the first release (`## ...`) of `CHANGELOG.md` when the catalog result holds no `ok` fact whose id starts with `openspec.`, and the fact MUST name `changelog` as its `source`.

#### Scenario: A repository without openspec
- **WHEN** a fixture checkout holds a `CHANGELOG.md` with Features or Bug Fixes items and the catalog result holds no `ok` OpenSpec fact
- **THEN** `functional.change` holds those items and names `changelog` as its `source`

### Requirement: The functional change falls back to the commit subjects
The project review SHALL record `functional.change` from the `feat` and `fix` commit subjects of its window when `CHANGELOG.md` gives no section items, and the fact MUST name `subjects` as its `source`.

#### Scenario: A repository with neither openspec nor changelog
- **WHEN** a fixture checkout holds no `ok` OpenSpec fact and no `CHANGELOG.md` section items, and its window holds `feat` and `fix` commits
- **THEN** `functional.change` holds those commit subjects and names `subjects` as its `source`

### Requirement: The functional change falls back to the merged pull request titles
The project review SHALL record `functional.change` from the titles of `listing.merged_titles` when no CHANGELOG section item and no `feat` or `fix` commit subject exists, and the fact MUST name `pull_requests` as its `source`, or record status `skipped` with `source` `functional` and a reason when all sources are empty.

#### Scenario: A repository with only pull request titles
- **WHEN** a fixture window holds no CHANGELOG section item and no `feat` or `fix` commit subject, and `listing.merged_titles` gives two merged pull request titles
- **THEN** `functional.change` holds the two titles and names `pull_requests` as its `source`

#### Scenario: All functional change sources are empty
- **WHEN** a fixture window holds no CHANGELOG section item, no `feat` or `fix` commit subject, and no merged pull request title
- **THEN** `functional.change` has status `skipped`, `source` `functional`, and a non-empty reason

### Requirement: The complexity rank is skipped when lizard reads no hot file
The project review SHALL keep churn order on `git.hotspots` and MUST record `lizard.complexity` as `skipped` with a reason when the window has hot files and lizard reads none of them, while empty hot files stay `ok` with `[]`, and `render_review` MUST show that skipped reason.

#### Scenario: A Shell-only repository
- **WHEN** a fixture window holds only Shell hot files
- **THEN** `complexity_fact` gives `status` `skipped` with a reason stating no hot file is readable by lizard, `git.hotspots` keeps the churn rank, and `render_review` includes that reason

## MODIFIED Requirements

### Requirement: The review writes the facts in a fixed order with the disagreements and the read counts
The facts in `data.json` SHALL be the commits, their types, the net change and the churn with generated paths apart, the release tags, the hot files and the complexity, the `functional.change` fact when the catalog result holds no `ok` fact whose id starts with `openspec.`, then each fact of the catalog in the catalog order. `data.json` SHALL also hold the disagreements, and the count of the reads of each reader kind with the seconds of the collection.

#### Scenario: The facts of a fixture catalog follow the git facts
- **WHEN** the review runs with a fixture catalog of two facts in the section `service` and no `ok` OpenSpec fact
- **THEN** `data.json` holds the git facts with section `changes`, then `functional.change` with section `changes`, then the two facts with section `service`, and the count of the reads of each reader kind

### Requirement: A dry run of the review starts no program
With a window option, `devops roadmap review run --dry-run` SHALL print the ordered git commands, shared reads, and catalog facts with read placeholders. With no window option, it SHALL list each `service.repos` repository with section titles, fact IDs, unset settings, and condition text. It SHALL start no program, send no request, open no connection, and write no file.

#### Scenario: A dry run lists the git commands
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --dry-run`
- **THEN** the output lists the `git log` command of each tag and the first-parent log of `<base commit>..<head commit>`, and no program starts

#### Scenario: A dry run lists the catalog queries and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run` with fakes of GitHub, Prometheus, Loki and the processes that record each call
- **THEN** the output lists each fact id of the catalog with its rendered query, and each fake records 0 calls

#### Scenario: A dry run with no window lists each repository of service.repos
- **WHEN** a person runs `devops roadmap review run --dry-run` with no window option while `service.repos` names 7 repositories and `prometheus.url` is unset, with fakes of GitHub, Prometheus, Loki and the processes recording each call
- **THEN** the output holds one block for each of the 7 repositories containing every catalog section title and fact id, `The setting prometheus.url has no value.` on `prometheus.*` facts, `the base and the head commits hold openspec/specs` on `openspec.*` facts, and zero calls on any fake

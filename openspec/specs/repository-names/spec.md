# repository-names Specification

## Purpose
Defines how devops-cli parses a GitHub repository one time and builds each name, label, lock name, Valkey key and telemetry value of that repository from one rule, so that each repository of the roadmap Service has one set of names.

## Requirements

### Requirement: A repository reference parses owner/name one time
`RepoRef` SHALL accept `owner/name` when each part holds only ASCII letters, digits, `-`, `_` and `.`, no part is `.` or `..`, and the owner holds no `.`, SHALL refuse other text with an error that names `owner/name`, and SHALL treat two spellings that differ only in case as one repository with one `key`.

#### Scenario: Two spellings
- **WHEN** `RepoRef("Owner/Repo")` and `RepoRef("owner/repo")` are compared
- **THEN** they are equal, both have the key `owner/repo`, and the first keeps the display `Owner/Repo`

#### Scenario: A name that starts with a dot
- **WHEN** `RepoRef("o/.github")` is made
- **THEN** it is accepted with the key `o/.github`

#### Scenario: Text that is not owner/name
- **WHEN** `RepoRef` gets `o/n/x`, `o.x/n` or `o/..`
- **THEN** it raises a validation error that names `owner/name`

### Requirement: Label values select one repository
The owner and repository label values SHALL each be a Kubernetes label value. A part that is a label value SHALL be the casefolded part with no hash. Another part SHALL get its alphanumeric core, cut to 54 characters, then `-` and 8 hex of the hash of `key`, or the hash alone when no core is left.

#### Scenario: A plain name
- **WHEN** the repository is `Example-Owner/My.Repo_Name`
- **THEN** the label values are `example-owner` and `my.repo_name`

#### Scenario: A name that starts with a dot
- **WHEN** the repository is `o/.github`
- **THEN** the repository label value is `github-` and the first 8 hex characters of the id

### Requirement: Unit names come from their inputs
A unit name SHALL be `devops-cli-<row>-<slug of the name>[-<item>]-<10 hex>`, a DNS label of 63 characters or fewer, where the hash is of `key`, the item and the input key. The same inputs SHALL give the same name for each spelling, and two repositories SHALL give two names.

#### Scenario: Two spellings of one repository
- **WHEN** a unit name is built for `Owner/REPO` and for `owner/repo` with one row, item and input key
- **THEN** the two names are equal

#### Scenario: A long name with the longest row
- **WHEN** a unit name is built for a 40-character name, the row `alternatives` and the item 999999
- **THEN** the slug is cut and the name has 63 characters

### Requirement: Lock names are ConfigMap keys
A lock name SHALL be `<row>-<owner>.<name>[-<item>]`, casefolded, and SHALL be a valid ConfigMap key.

#### Scenario: A lock with an item
- **WHEN** the lock name of the row `refine` and the item 42 is built for `Example-Owner/Devops-CLI`
- **THEN** it is `refine-example-owner.devops-cli-42`

### Requirement: Two patterns find the keys of one repository
A `valkey-roadmap` key of a repository SHALL be `roadmap:v1:<kind>:<key>[:<id>]` and a key of the installation `roadmap:v1:<kind>[:<id>]`. A kind or id that is empty or holds `/` or a glob character SHALL be refused. The two patterns of a repository SHALL find each of its keys and no other key.

#### Scenario: Keys of two repositories and of the installation
- **WHEN** a Valkey server holds keys of two repositories and of the installation
- **THEN** `KEYS` with the two patterns of the first repository returns only the keys of the first repository

#### Scenario: A slash in an id
- **WHEN** a key is built with the id `a/b`
- **THEN** a validation error is raised

### Requirement: service.repos names each repository once
The settings SHALL refuse a `service.repos` entry that is not `owner/name`, and two entries with one `key`, with an error that names `service.repos`. They SHALL keep the GitHub spelling of each entry.

#### Scenario: Two spellings in service.repos
- **WHEN** `service.repos` is `[Owner/Repo, owner/repo]`
- **THEN** the settings do not load, and the error names `service.repos`

#### Scenario: An entry with no owner
- **WHEN** `service.repos` holds `no-owner`
- **THEN** the settings do not load, and the error names `service.repos`

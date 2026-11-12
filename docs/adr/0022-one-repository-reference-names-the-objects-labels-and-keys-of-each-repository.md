---
status: accepted
date: 2026-11-11
decision-makers: [owner]
issue: 4533
amended-by: ["0023"]
body-hash: 2522b325351f8369fcd3842d9cd4489d7b5278c26ceaf14a87a9a939599b8f86
---

# One repository reference names the objects, labels and keys of each repository

The roadmap Service works on 7 repositories of 1 owner. The move of its work to Kubernetes Jobs, Argo Workflows and Valkey (#4517) adds Jobs, Workflows, locks, Valkey keys, labels and telemetry values for each repository. This record gives one rule for each name, label, annotation, key and telemetry value that holds a repository. One value type, `RepoRef` in `src/devops_cli/github/repo_ref.py`, builds them.

## Context

On 2026-11-11 the owner recorded the go of ADR 0008 on #1535: the warm p95 was 11 seconds, against the limit of 30 seconds. On the same day the owner decided to move the Service work to Jobs and Argo Workflows, with Valkey as the shared state, and asked for owner and repository namespacing of the names of Kubernetes objects and of data keys.

Before this record, each part made names in its own way. Seven `.split("/")` calls parsed `owner/name`. The roadmap store, the cluster Job module and the Service each had a different check of a repository name. No collision was live, but these gaps lost the identity of the repository:

| Gap | Effect |
| :--- | :--- |
| A runner Job name holds no repository and no item. | `kubectl get jobs` does not show the repository or the item. |
| The Job label `implement-repo` has no prefix, and only the implement row uses it. | Other rows cannot use it. |
| The progress annotations are on the Job only. | Loki and `kubectl get pods` cannot find the pods of one repository. |
| A metric `repo` value has the spelling of the configuration, and Argo CD metrics use the same label name. | `label_values(repo)` with no metric name mixes the two. |
| The span attribute `service.repo` is a custom name. | Trace queries cannot use the OpenTelemetry VCS names. |
| A planned unit name did not start with `devops-cli-`. | Argo CD shows each unit Job and unit Workflow as an orphan. |

Three collisions were latent. `service.repos` had no check, so two spellings of one repository gave two folders and two sets of keys. A path put the folder `stage` on the same level as owner names. The Qdrant field `project_name` had two possible forms.

The names must obey these limits:

| Limit | Value |
| :--- | :--- |
| Label value | 63 characters or fewer; empty, or starts and ends with an alphanumeric, with `-`, `_` and `.` between. No `/`. |
| Job name and Workflow name | A DNS label of 63 characters or fewer. The Job controller copies the Job name into a pod label, and `argo lint` refuses a longer Workflow name. |
| ConfigMap key | `[-._a-zA-Z0-9]+`. |
| Argo lock name (v4.1.5) | A mutex name can hold `/`, but a semaphore key cannot. |
| Valkey `SCAN MATCH` and ACL patterns | Glob patterns. `*`, `?`, `[`, `]` and `\` are special, and `*` spans `:`. |
| GitHub names | ASCII letters, digits, `-`, `_` and `.`; not `.` or `..`; case is not significant. An owner holds no `.`. |

## Decision

`key` is the casefolded `owner/name`. `display` is the GitHub spelling. `hN(x)` is the first N hex characters of the sha256 of `x`.

### 1. One value type

- `RepoRef` parses `owner/name` one time, at the edge: a setting, a command option or a webhook payload. Each part must be a GitHub name, and the owner must hold no `.`. A name that starts with `.`, such as `.github`, is valid.
- Two `RepoRef` values are equal when their `key` values are equal.
- `id` is `h16(key)`. This is the value of the Job label `implement-repo`, so the labels of running Jobs stay valid.
- `service.repos` refuses an entry that is not `owner/name`, and two entries with one `key`. The error names `service.repos`.
- Data keys, annotations and telemetry use `key`. Answers and text for people use `display`.

### 2. Object names

- **Slug.** Casefold. Change each run of characters outside `[a-z0-9]` to `-`. Remove `-` from both ends. Cut to the budget, then remove `-` from the end. If nothing is left, use `x`.
- **Unit name** (the one Job or Workflow of a row for one item, issue or batch): `devops-cli-<row>-<slug(name)>[-<n>]-<h10(key, n, input key)>`, 63 characters or fewer. The same inputs give the same name, so a second create gets 409, and this covers a create that timed out but succeeded. The labels, not the name, find the unit of an item.
- **Ad hoc name**: `devops-cli-<what>-<slug(name)>[-<n>]-<6 random hex>`. Only a Job of `devops k8s run-job` and the runner Job use it, until the implement Workflow (#3105) replaces the runner Job.
- The rows are `implement`, `stage`, `refine`, `alternatives`, `intake`, `sweep`, `metrics`, `brain` (ADR 0023), `resolve`, `group`, `split`, `watch`, `fix-checks`, `fix-conflict` and `fix-plan` (ADR 0021 section 8). A unit with no item has no `-<n>`.
- The prefix `devops-cli-` keeps each name in the Argo CD orphan glob `devops-cli-*`. The slug is cut, and the hash keeps the identity. With the longest row, `alternatives`, and a 6-digit item, the slug of a long name is cut to 21 characters, and the unit name has 63 characters.
- A row name has at most 12 characters, the length of `alternatives`, so the rule above holds for each row. No row has the name `repair`, because that word names three things already: the command `devops roadmap repair`, the read-back repair of job records and the repair task of `brain-daily`.
- A unit of `fix-checks` or `fix-conflict` fixes one pull request of an item. Its `<n>` is the item, and its input key holds the number of the pull request, the head and the check or the base (ADR 0021 section 8).
- `watch` is a step of the sweep and has no unit. Its row name gives its lock name and its due mark.
- `fix-plan` runs as the row `fix_plan` of the model lane of the Service until the sweep step (#4574), and has no unit until then. Its unit has the item as `<n>`, and its input key holds the number of the plan pull request and the head.
- `ServiceRow` in `src/devops_cli/github/repo_ref.py` gets the member of a row in the item that builds the row: `BRAIN`, `RESOLVE`, `GROUP`, `SPLIT`, `WATCH`, `FIX_CHECKS` and `FIX_CONFLICT`.

### 3. Labels, annotation and service name

Each Service Job, Workflow and pod carries these keys. A Workflow carries them in `metadata.labels` and in `spec.podMetadata.labels`.

| Key | Value |
| :--- | :--- |
| `app.kubernetes.io/name` | `devops-cli-job`, unchanged. The NetworkPolicies and the admission policy select by it. |
| `app.kubernetes.io/component` | `roadmap-<row>` |
| `app.kubernetes.io/part-of` | `devops-cli-stack` |
| `app.kubernetes.io/managed-by` | `roadmap-service`, or `devops-cli` for `devops k8s run-job` |
| `roadmap.devops-cli/owner` | the owner label value |
| `roadmap.devops-cli/repo` | the repository label value |
| `roadmap.devops-cli/item` | the issue number |
| `implement-repo` | `id`, on implement Jobs only |
| annotation `roadmap.devops-cli/repository` | `key` |
| environment variable `OTEL_SERVICE_NAME` | `roadmap-<row>`. The router keeps `roadmap-service`. |

- **Label values.** The owner value is the casefolded owner, and the repository value is the casefolded name, when the part is a label value. Else the value is the part with no non-alphanumeric characters at its ends, cut to 54 characters, with no `.`, `_` or `-` at its end, then `-` and `h8(key)`. If nothing is left, the value is `h8(key)`. A plain value is the exact part, and a changed value holds the hash, so the pair of the two values selects one repository.
- A label value cannot hold `/`, so no single label holds the full repository.
- `implement-repo` stays until no code lists Jobs by it. A new Service that lists by a new key does not see a runner Job that an older Service made, and it can start a second implement Job for the repository.
- The annotation goes on the pod template too, so the log collector can make it a stream label.

### 4. Lock names

A mutex name and a ConfigMap key that hold a repository use `<row>-<owner>.<name>[-<n>]`, casefolded. An owner holds no `.`, so the name splits at its first `.`. A row uses one form: always with an item, or never. One form for mutexes and semaphore keys removes the question of `/`.

### 5. Valkey keys

In `valkey-roadmap`:

```text
roadmap:v1:<kind>:<owner>/<name>[:<id>]   state of one repository
roadmap:v1:<kind>[:<id>]                  state of the Service or of the installation
```

- `<owner>/<name>` is `key`. A kind and an id hold no `/` and no glob character.
- The keys of one repository are `SCAN MATCH roadmap:v1:*:<owner>/<name>` and `SCAN MATCH roadmap:v1:*:<owner>/<name>:*`. The repository part holds the only `/` of a key, and the part after it starts with `:`. So `o/n` never matches a key of `o/nn` or of `xo/n`, and a key of the Service never matches.
- A second owner gets the ACL pattern `~roadmap:v1:*:<owner>/*`. The role ACLs select by kind.
- Each Valkey instance has one owner, so the instance is the namespace. `valkey-devops` keeps its `valkey:` cache keys, and `valkey-runs` keeps its keys. No key has a hash tag, because each instance is a single instance.

### 6. Telemetry

- **Metrics.** The label `repo` is `key` for a repository of `service.repos`, else `other`. A metric label never holds an item number, a unit name, a branch or a pod name. A dashboard reads the variable with a metric name.
- **Logs.** The log collector maps the pod annotation `roadmap.devops-cli/repository` to the stream label `repo` on unit pods. The router and the sweep serve all repositories, so they put `repo` in the JSON field of each line.
- **Traces.** Round and unit spans carry `vcs.provider.name=github`, `vcs.owner.name` and `vcs.repository.name` (the casefolded parts of `key`), in place of `service.repo`. The item number is a span attribute only.

### 7. Paths and branches

- After the move, only clones stay on the volume. The clone path is `<data>/roadmap/repos/<owner>/<name>/clone/`, casefolded. The level under `repos/` holds owners only.
- Branch names do not change. A key outside the repository that names a branch or an item also holds `key`.

### 8. Namespaces

Namespaces do not change. The installation is the identity (ADR 0015), so if a second GitHub App installation comes, it gets a namespace of its own, `devops-<owner>`, with its own Secret and templates.

### 9. Data of a removed repository

The sweep deletes the data of a repository that `service.repos` has not named for 7 days: its keys (the two patterns, then `UNLINK`) and its clone folder. A gauge counts the repositories that wait. The wait keeps a typing error in the configuration from deleting plan records. The caches in `valkey-devops` expire by their TTL.

## Considered Options

- **Kubernetes `metadata.generateName`**: rejected for Service work. The claim record names the Job before the create, a dry run must show the name with no request, and a repeated create must get 409.
- **`python-slugify`**: rejected. GitHub names are ASCII, so one `re.sub` makes the slug.
- **The Helm pattern `trunc 63 | trimSuffix "-"`**: adopted, with a hash that keeps the identity.
- **A label value check of the Kubernetes client**: `kubernetes==36.0.3` has no public check, so `CONST_K8S_LABEL_VALUE_RE` holds the rule.
- **OpenTelemetry VCS semantic conventions**: adopted for span attributes, through the constants of `opentelemetry-semantic-conventions`.
- **The repository before the kind in Valkey keys** (`roadmap:v1:<owner>/<name>:<kind>`): rejected. The role ACLs and the schema version select by kind, and `*` spans `:`, so two patterns find one repository in the kind-first order.
- **A new prefix for every cache key** (`devops-cli:<repo>:...`): rejected. The instance is the namespace, and a new prefix makes about 2,400 cache keys miss once and adds no isolation.
- **A rename of `implement-repo` now**: rejected. The Service rolls about 15 times a day, and a runner Job runs for up to 4 hours, so a new Service would not see a running Job.
- **A namespace for each owner now**: rejected until a second installation exists.
- **A Qdrant collection for each repository**: rejected. When a second repository goes into Qdrant, its points get a payload field `repo` = `key` with a keyword index and `is_tenant: true`.

## Consequences

- Each consumer moves to `RepoRef` in the item that changes it, and its old helper goes in the same pull request: the Job labels and names (#4558), the logs and traces (#4576), the plan records (#4564), the clone path (#4574) and the cleanup of a removed repository (#4603).
- The engine step (#4566) changes the Argo CD orphan glob for Workflows from `devops-cli-version-*` (ADR 0008) to `devops-cli-*`, and runs one mutex of the form of section 4 on the live controller.
- A configured spelling with capital letters changes its metric series one time, when the metrics use `key`. No alert or panel pins a `repo` value.
- The settings refuse a bad `service.repos` before any job starts.
- No new runtime dependency.

## Status History

Amended on 2026-11-11 by [ADR 0023](0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md). Section 2 gets the row `brain`.

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md` names the merge commit.

This record supersedes no record and amends no record. The record of the move of the Service work (#4527) uses the names, labels and keys of this record.

The pull request of #4792 amends section 2 on 2026-11-12. It adds the rows `resolve`, `group`, `split`, `watch`, `fix-checks` and `fix-conflict` of ADR 0021 section 8, and the rule for the length of a row name. The merge of that pull request is the approval of the amendment.

The pull request of #5061 amends section 2 on 2026-11-12. It adds the row `fix-plan` of ADR 0021 section 8. The merge of that pull request is the approval of the amendment.

2026-11-12: Fact out of date: the record of the move of the Service work is [ADR 0021](0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) (#4617).

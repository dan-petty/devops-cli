# `devops review`

AI-powered multi-persona code review and security audits.

## Commands

## `devops review path`

**Review source files directly (no git required).**

```bash
devops review path [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | No | File(s) or directory(ies) to review. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--watch`, `-w` | `boolean` | - | Continuously watch target paths for changes and re-run reviews. |
| `--debounce-ms` | `integer` | `500` | Debounce window in milliseconds for filesystem watcher. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

---

## `devops review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

---

## `devops review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | Target repository in OWNER/REPO format. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

---

## `devops review findings`

**Inspect structured findings for a review session.**

Inspect structured findings for a review session.

Each finding keeps its number, its place in findings.json, whatever filter the list
applies, and `devops review verify --index` takes that number. With `--candidates` the list
is candidates.json: every finding the review raised, the ones verification invalidated
included, numbered for `devops review verify --candidate`.

```bash
devops review findings [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED. |
| `--unverified` | `boolean` | - | Show unverified findings only. |
| `--invalidated` | `boolean` | - | Show INVALIDATED findings only; add --candidates to look among every finding the review raised. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--mitigated` | `boolean` | - | Filter findings by MITIGATED status |
| `--candidates` | `boolean` | - | List candidates.json: every finding the review raised, reported or not. |
| `--severity` | `string` | - | Show only findings of this severity: CRITICAL, HIGH, MEDIUM, LOW or INFO (repeatable). |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

---

## `devops review verify`

**Record a person's verdict on a review finding or candidate.**

Record a person's verdict on a review finding or candidate.

Name one finding: `--index` takes the number `devops review findings` shows, `--title` a
substring of exactly one title, and `--candidate` the number `review findings --candidates`
shows. There is no default verdict, so `--status` is required. A candidate given VERIFIED
or MITIGATED moves into findings.json, unless findings.json already reports its defect under
another title: give that finding the verdict instead.

A verdict on a finding in findings.json is recorded on the candidate it reports too, and a
verdict on a candidate on its copy in findings.json, so both lists agree. When that copy also
reports another candidate of the same persona, title, location and description, give the
verdict to the copy with `--index`. Verdicts given on one session at once take turns.

The verdict is a label on the session's files and ranks review history; later reviews do not
learn from it. To stop a false positive coming back, add a `[[suppressions]]` entry with a
reason and an expiry to `.devops/review.toml`.

```bash
devops review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--index`, `-i` | `integer` | - | Number `review findings` shows for the finding: its place in findings.json, whatever filter the list applied. |
| `--title`, `-t` | `string` | - | Substring of exactly one finding title in findings.json. |
| `--candidate` | `integer` | - | Number `review findings --candidates` shows; a VERIFIED or MITIGATED verdict moves the candidate into findings.json. |
| `--status` | `string` | - | Verdict to record (required): VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |

---

## `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

---

## `devops review benchmark`

**Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage.**

```bash
devops review benchmark [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | Yes | File(s) or directory(ies) to review on every run; keep them fixed to compare benchmarks. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--runs`, `-n` | `integer` | `3` | Number of reviews to run; the report takes medians across them. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review. |

---

## `devops review score`

**Score saved review sessions against a label file: precision, recall and stability, each with its n.**

```bash
devops review score [OPTIONS] <sessions>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sessions>` | `path` | No | Review session directories to score. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--labels` | `path` | - | Label file: the labelled inputs, the row map of each mapped session and the labels, such as tests/fixtures/review_labels/labels.json. |
| `--materialise-golden` | `path` | - | Write the label file's golden set into this directory as a git repository with one fixed commit, for a path review, and list the defects no tool can express. Takes no sessions. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops review export-feedback`

**Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.**

Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.

Each session's findings.json and candidates.json are read, and only the findings whose
verdict the dataset does not hold yet are appended. An export that finds none leaves the
dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset
changes no prompt and no later review.

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | JSONL dataset to append to (default: the configured data.feedback_dataset_path). |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

---

## `devops review corpus`

```bash
devops review corpus COMMAND [ARGS]...
```

### `devops review corpus generate`

**Copy source files with one known defect injected into each, and record where.**

```bash
devops review corpus generate [OPTIONS] <sources>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sources>` | `path` | Yes | Clean file(s) or directory(ies) to inject defects into; each becomes a folder of the corpus. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--out`, `-o` | `path` | - | Corpus directory to create (default: corpora/\<source\>-\<seed\> under the reviews directory). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--template`, `-t` | `string` | - | Defect template to inject (repeatable; default: all). |

### `devops review corpus score`

**Score one arm of reviews of a corpus: which injected defects each run found, and what verification kept.**

```bash
devops review corpus score [OPTIONS] <corpus_dir>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<corpus_dir>` | `path` | Yes | Corpus directory created by `devops review corpus generate`. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Review session to score (repeatable; default: the latest review of the corpus). The sessions must have run the same review prompts. |
| `--runs`, `-n` | `integer` | - | Score the latest N reviews of the corpus together as one arm: how many runs found each injection, and each figure's mean and range across the runs. Refused with --session. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops review samples`

```bash
devops review samples COMMAND [ARGS]...
```

### `devops review samples list`

**List the sample catalog, and whether each sample is fetched at its commit.**

```bash
devops review samples list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

### `devops review samples fetch`

**Fetch samples at their pinned commits, verifying commit, licence files and paths.**

```bash
devops review samples fetch [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to fetch (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops review samples validate`

**Run devops ai tooling over fetched samples and save a JSON report per category.**

```bash
devops review samples validate [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to validate (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--review` | `boolean` | - | Also review each category's synthetic defect corpus and score it (calls the configured LLM). |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |

---

## `devops review templates`

```bash
devops review templates COMMAND [ARGS]...
```

### `devops review templates list`

**List registered synthetic defect templates and their supported languages.**

```bash
devops review templates list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops review templates sweep`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops review templates sweep [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops review templates check`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops review templates check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

---

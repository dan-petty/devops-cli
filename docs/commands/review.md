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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--watch`, `-w` | `boolean` | - | Continuously watch target paths for changes and re-run reviews. |
| `--debounce-ms` | `integer` | `500` | Debounce window in milliseconds for filesystem watcher. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--invalidated` | `boolean` | - | Show invalidated findings only. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--mitigated` | `boolean` | - | Filter findings by MITIGATED status |
| `--candidates` | `boolean` | - | List candidates.json: every finding the review raised, with the ones verification dropped. |
| `--severity` | `string` | - | Show only findings of this severity: CRITICAL, HIGH, MEDIUM, LOW or INFO (repeatable). |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

---

## `devops review verify`

**Record a person's or an agent's verdict on a review finding or candidate.**

Record a person's or an agent's verdict on a review finding or candidate.

Name one finding: `--index` takes the number `devops review findings` shows, `--title` a
substring of exactly one title, and `--candidate` the number `review findings --candidates`
shows. There is no default verdict, so `--status` is required. A candidate given VERIFIED
or MITIGATED moves into findings.json, unless findings.json already reports its defect under
another title: give that finding the verdict instead.

A verdict on a finding in findings.json is recorded on the candidate it reports too, and a
verdict on a candidate on its copy in findings.json, so both lists agree. When that copy also
reports another candidate of the same persona, title, location and description, give the
verdict to the copy with `--index`. Verdicts given on one session at once take turns.

`--adjudicator` records who gave the verdict: `human`, the default, or `agent`, which an AI
agent passes and the MCP `verify_finding` tool always sends. An agent cannot change a
person's verdict. Only a person's verdict ranks review history, teaches the learned catalog
(INVALIDATED) or records a mitigation in the ledger (MITIGATED). A reset to UNVERIFIED
withdraws what the finding's verdicts recorded there: an entry another verdict also
recorded stays, and one nothing else recorded is removed.

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
| `--status` | `string` | - | Verdict to record (required): VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. UNVERIFIED also withdraws what a person's verdicts recorded in the catalog and ledger. |
| `--adjudicator` | `choice (human|agent)` | `human` | Who gives the verdict: human, or agent for an AI agent, which cannot change a person's verdict. Only a person's verdict ranks review history and teaches the learned catalog and mitigations ledger. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |
| `--perimeter`, `-p` | `string` | - | Perimeter file path(s) protecting against finding recurrence (repeatable). |
| `--regression-test` | `string` | - | Path to regression test guarding against finding recurrence. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |

---

## `devops review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset. |
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
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
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
| `--save`, `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
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
| `--save`, `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

---

## `devops review hallucinations`

```bash
devops review hallucinations COMMAND [ARGS]...
```

### `devops review hallucinations list`

**List catalog entries: builtin ones shipped with the tool, and learned ones from this workspace.**

```bash
devops review hallucinations list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--learned` | `boolean` | - | Show learned entries only. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops review hallucinations remove`

**Remove learned catalog entries; builtin entries cannot be removed.**

```bash
devops review hallucinations remove [OPTIONS] <ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ids>` | `string` | No | Ids of learned entries to remove. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all-learned` | `boolean` | - | Remove every learned entry. |

---

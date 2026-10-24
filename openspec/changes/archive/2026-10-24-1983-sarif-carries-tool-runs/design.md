# Design

## Context

See proposal.md, Why. `ToolRun` (`src/devops_cli/security/tool_executor.py`) is the record of one run of a review tool: `tool`, `version`, `binary_sha256`, `executor`, `config_digest`, `ruleset_digest`, `argv_template`, `targets_digest` and `commit`. The record is built before the tool starts. `RecordingToolExecutor` keeps the records of a review. `to_sarif` (`src/devops_cli/security/sarif.py`) gives each tool its own SARIF run. The review calls it with no scanner outcomes, so only a tool that gave a result has a run.

The sections below are from the OASIS SARIF 2.1.0 specification, Errata 01.

## Goals / Non-Goals

**Goals:**

- The SARIF run of a tool holds every record of that tool, with no change to its values.
- The document writes a SARIF name only where the record holds each value that SARIF requires there.
- Each emitted document validates against the vendored SARIF 2.1.0 schema.

**Non-Goals:**

- A record of the exit code, or of the success of a run. A follow-up holds these.
- A repository URI in the record.
- Records in the SARIF document of `devops scan`, which keeps no records.

## Decisions

### Decision 1: The records go in the property bag of the run of their tool

The run of a tool holds `properties.tool_runs`, a list of the records of the tool in the order of the runs. Each record is `ToolRun.model_dump(mode="json")`, so `ToolRun.model_validate` reads it back. A property bag is "an object containing an unordered set of properties with arbitrary names", and its values "MAY be of any JSON type" (section 3.8.1). Its names SHOULD be camelCase, but a converter "SHOULD use a property name that matches the name of that piece of information in the native tool format" (Appendix D). devops-cli converts the output of its tools to SARIF, and `tool_runs` and the field names of `ToolRun` are the names of `profile.json`. So one set of names stands for the records in both files. Appendix D also says that a converter "SHOULD populate those elements of the SARIF format for which a direct equivalent exists". The driver name and the driver version are the direct equivalents that the record holds (Decision 2).

- **Rejected alternative**: one row for each distinct record, with a count of its runs, as `review.md` shows them. The table leaves out the targets digest, so the SARIF document would hold less than the record. The size of the document grows with the number of runs, and this is accepted.

### Decision 2: The driver takes the version of the records only when no result names one

The version that a result names is the version that the tool reported in its output. It stays first, as before. When no result names a version and the records of the tool name one version, `tool.driver.version` is that version. Records that name two versions do not say which version gave the results, so the driver names none.

### Decision 3: A record gives no tool a run

A run with no results says that the tool ran and found nothing: "If the tool did not detect any results, results SHALL be an empty array" (section 3.14.23). A record does not say that the tool succeeded. A scanner that failed may have a record, because the record is built before the tool starts. In GitHub code scanning, a run with no results also closes the open alerts of its tool. So a tool that has records and no result gets no run. The document of `devops scan` keeps its rule, with scanner outcomes: a scanner whose outcome is `ran` gets a run, also with no results. This answers the question that the issue left to a person.

- **Rejected alternative**: a run for every tool that has a record. Rejected, because the run of a tool that failed would say that the tool found nothing.

### Decision 4: No invocation for a record

`argv_template` fits `invocation.commandLine`: "the completely specified command line used to invoke the tool" (section 3.20.2). But "An invocation object SHALL contain a property named executionSuccessful whose value is a Boolean that is true if the engineering system that started the process knows that the analysis tool succeeded" (section 3.20.14). Its note says: "This property is needed because not all programs exit with an exit code of 0 on success and non-0 on failure." A scanner decides success from the exit code and the parsed output together (`_handle_json_output` in `src/devops_cli/security/base.py`). The record does not hold this decision. So the document writes no invocation for a record.

- **Rejected alternative**: add the exit code to `ToolRun`, as the issue asks, and write `executionSuccessful` from it. Rejected, because section 3.20.14 says that the exit code does not tell success. Gitleaks and Semgrep exit with 1 when they find a result. The exit code alone would fill `invocation.exitCode` (section 3.20.9), which needs an invocation. The record is built before the run, and the shared `ToolExecutorFake` builds it in the same way, so the field would also change the fake and its contract suite. A follow-up adds the exit code and the success of the run together.
- **Note for the follow-up**: the placeholders `{targets}`, `{config}` and `{ruleset}` stand for paths, so a `commandLine` from the template is a redacted string. "If the value of any redactable property (§3.5.2) in theRun has been redacted, theRun SHALL contain a property named redactionTokens" (section 3.14.28). `commandLine` is redactable (section 3.20.2), and any readily identifiable string can be a token.

### Decision 5: No artifact for the binary digest or the file digests

The role `driver` means "The file belongs to the analysis tool's driver" (section 3.24.6). But "If the artifact object represents a top-level artifact, then location SHALL be present" (section 3.24.2). The record holds no path of the binary. A host path can also disclose the layout of the machine (section 3.20.18, note 3).

A hash "SHALL be a string representation of the hash digest of the artifact, computed by the hash function specified by the property name" (section 3.24.11). The config, ruleset and targets digests are the first 16 digits of a SHA-256 over a sorted list of file digests (`digest` in `src/devops_cli/ai/run_store.py`). None of them is the SHA-256 of one artifact, and the record holds no path of the files.

- **Rejected alternative**: `run.artifacts` with `hashes` and `roles` and no location, as the issue asks. Rejected for the two reasons above.

### Decision 6: No `versionControlProvenance` for the commit

"A versionControlDetails object SHALL contain a property named repositoryUri whose value is a string containing an absolute URI" (section 3.23.3). The record holds no repository. `revisionId` "uniquely and permanently identifies the appropriate revision of the scanned files" (section 3.23.4). A commit that ends with `-dirty` names no such revision. So the commit stays in the record.

- **Rejected alternative**: read the remote URL of the checkout when the document is written, as the issue asks. Rejected, because the record does not hold it, and a checkout can have no remote or an SSH address that is no absolute URI. A follow-up can add the repository to the record.

## Risks / Trade-offs

- [A review that starts a tool once for each file writes one record for each run] → The document grows by one record for each run. `profile.json` already holds each record.
- [The meaning of `binary_sha256` for a Python tool changes in #1984] → The document copies the record and does not interpret the value, so that change needs no change here.
- [A result of a tool whose SARIF run has another name, such as `c901` from Ruff, gets no records] → The records go to the run whose driver has the name of the tool. This change does not rename runs.

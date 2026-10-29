# Design

## Context

See proposal.md, Why. An executor builds the `ToolRun` of a run with `record_tool_run` before the tool starts, and answers with a `ToolResult`: the record, the exit code, the output and whether the run timed out. `RecordingToolExecutor` keeps the record of each run of a review. A scanner then decides the outcome of its scan from the exit code and the parsed output. Decision 4 of the #1983 change wrote no invocation, because the record did not hold that decision.

The quoted sections are from OASIS SARIF 2.1.0 Errata 01.

## Goals / Non-Goals

**Goals:**

- The record of a run holds its exit code and its success, as the code that ran the tool decides it.
- The run of a tool in `findings.sarif` holds one invocation for each record whose success is known, and the redaction tokens of its command lines.
- Each emitted document validates against the vendored SARIF 2.1.0 schema.

**Non-Goals:**

- The repository of the checkout and `versionControlProvenance` (#2101).
- `exitSignalName` and the times of each invocation. The record holds neither.
- Records in the SARIF document of `devops scan`, which keeps no records.

## Decisions

### Decision 1: The code that ran the tool settles the run through the executor

`ToolExecutor` gets one method, `settle(result, *, success)`. The code that called `run` decides if the run succeeded and calls `settle` with the result once. `RecordingToolExecutor.settle` finds the record of the run by identity and puts `result.settled(success=...)` in its place. So the records stay in the order the runs started. A result that the recorder did not start, or that is already settled, raises `ValueError`: that is a defect of the caller. The direct executor, the sandbox executor and `ToolExecutorFake` keep no records, so their `settle` does nothing.

- **Rejected alternative**: the executor decides success from the exit code. Section 3.20.14 says that the exit code does not tell success. Gitleaks and Semgrep exit with 1 when they find a result, and mypy exits with 1 when it finds an error.
- **Rejected alternative**: the request carries a function that decides success from the result. The scanner decides from its parsed output, so the function would parse the output a second time.
- **Rejected alternative**: the recorder keeps only settled records. A run whose caller raised before it settled would then leave no record, and the record says what ran.
- **Rejected alternative**: a mutable `ToolRun`. The record is a frozen model so that `tool_run_rows` can count equal records, and a record that changes after the recorder keeps it could change a row of the report.

### Decision 2: The settled record takes its exit code from the result

`ToolResult.settled` copies the record with `exit_code` and `success`. The exit code is the exit code of the result. It is empty when the run timed out, because the executor ended the process, and when the exit code is negative, because a signal ended the process. "If the SARIF producer process exited due to a signal, the exitCode property SHALL be absent" (section 3.20.9). The exit code 124 of a timed-out result is a value of the executor, not of the tool.

- **Rejected alternative**: each executor writes the exit code in the record of its result. The direct executor, the sandbox executor and the fake would each need the rule for signals and timeouts, and a record would hold the exit code in two places of the result.

### Decision 3: A scan succeeded when its outcome is `ran` or `coverage_gap`

The scanner base settles a run after it decides the outcome of the scan. `ran` means that the tool ran and its output was read. `coverage_gap` from a result means that the tool ran and its own report names the files that it left out. Every other outcome of a run that started (`failed`, `built-in patterns`, a timeout, and an error while the output is read) says that the tool did not succeed. mypy succeeded when it ended with exit code 0 or 1, the codes of a finished check. The SBOM of Trivy succeeded when Trivy ended with exit code 0. A canary succeeded when its gate passed.

### Decision 4: One invocation for each settled record

The run of a tool writes an invocation for each record of the tool whose `success` is known, in the order of the runs (section 3.14.11). The invocation holds `executionSuccessful` from `success`, `exitCode` when the record holds one, and `commandLine`. `commandLine` is the argument template of the record. Each argument is quoted with `shlex.quote`, except a placeholder, which stays as it is. When the run of a scanner comes from scanner outcomes and no record of the scanner is settled, the run keeps the invocation of its outcome, as before.

- **Rejected alternative**: `invocation.arguments` from the template. Section 3.20.3 does not call `arguments` redactable, so it cannot hold a placeholder in place of a path.

### Decision 5: The placeholders are the redaction tokens of the run

The placeholders stand for paths of the host, so a command line from the template is a redacted string (section 3.20.2). "If the value of any redactable property (§3.5.2) in theRun has been redacted, theRun SHALL contain a property named redactionTokens" (section 3.14.28). The run lists each placeholder that one of its command lines holds, in the order targets, config, ruleset. A run whose command lines hold no placeholder has no `redactionTokens`.

### Decision 6: Each tool that has a record has a run

Decision 3 of the #1983 change gave no run to a tool with records and no result, because a record did not say that its tool succeeded. A settled record says it. So each tool that has a record gets a run in the document of a review:

- The tool gave a result: the run holds its results, as before.
- The tool gave no result, and every record of the tool succeeded: the run has an empty `results` array. "If the tool did not detect any results, results SHALL be an empty array" (section 3.14.23).
- The tool gave no result, and a record failed or is not settled: the run has no `results`, which "SHALL default to null". The schema types `results` as an array, so the document leaves it out rather than write null.

CI does not upload `findings.sarif` to code scanning, so no run of a review closes an alert there.

- **Rejected alternative**: keep the rule of #1983 and give no run to a tool with no result. Then the records of a clean tool, and their invocations, would not be in the document, and the issue asks for an invocation for each record.

### Decision 7: The Tool Runs table shows the exit code and the success

`tool_run_rows` counts equal records, and the exit code and the success are now part of a record. Two records that differ only in them make two rows. So the table gets the columns `Exit code` and `Succeeded`. Otherwise two rows would read the same.

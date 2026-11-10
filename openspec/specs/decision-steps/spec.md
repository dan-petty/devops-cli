# decision-steps Specification

## Purpose
A decision step is a place in a workflow where Jev (a System One decision model) gives evidence for a pick among a few known outcomes. This capability fixes the rules that every decision step follows: a closed question set, an evidence builder that tools run, thresholds fitted on labelled data, action bands, a shadow log and a fail-open rule. The rules come from ADR 0019.

## Requirements

### Requirement: A decision step uses a closed question set
A decision step SHALL ask Jev only the questions of a set that its code fixes. Each question SHALL be a yes/no, a choice or a score question about one short piece of evidence. A decision step SHALL NOT write a text, a quote or a finding from a Jev answer.

#### Scenario: The question set is fixed
- **WHEN** a test builds the request of a decision step for two different inputs
- **THEN** both requests hold the same question names for the same kinds of piece, and no question text comes from the input

#### Scenario: The step writes no text
- **WHEN** Jev answers a request of a decision step
- **THEN** the outcome of the step is one band of the closed set, and no text of the answer reaches a comment, a finding or a file

### Requirement: Tools extract the evidence
A decision step SHALL build the state of a request in code from the input, as a digest of short pieces and of facts that tools found: a hunk, a path, a quoted line, a test name, a criterion or a fact of a tool call. Each piece SHALL be limited in size. The state of a request SHALL NOT be the whole document.

#### Scenario: A long input is cut to a digest
- **WHEN** the evidence builder gets an input with long texts
- **THEN** the state it returns holds each text cut to its size limit, and holds the facts that the tools found as facts

### Requirement: Cuts are data that a fit set
A decision step SHALL read the cuts of its questions from a data file in the repository. The file SHALL record the model, the date, the cases of the fit and the numbers that gave each value. A decision step SHALL NOT take a cut from a constant that nobody fitted.

#### Scenario: Thresholds are data
- **WHEN** a test loads the thresholds of a decision step
- **THEN** each question of the step has a cut in the data file, and the file names the model and the cases of its fit

### Requirement: The fit uses fixed halves and is repeated
A fit SHALL use one fixed half of the labelled cases, and the report SHALL use the other half. The fit SHALL repeat with the halves swapped. It SHALL run with a cut for each question and with one cut for all questions, and the report SHALL give the loss of both and the number of cases in each half.

#### Scenario: The halves are fixed
- **WHEN** the fit command runs twice on the same cases
- **THEN** it uses the same two halves both times, and it reports the numbers of the half that it did not fit

### Requirement: The success bar is checked against its oracle
The report of a decision step SHALL state the oracle: the most cases that any step can skip with no loss on its labelled data. A success bar that asks for more than the oracle SHALL NOT be set.

#### Scenario: The oracle is reported
- **WHEN** the fit command reports a step
- **THEN** the report gives the oracle beside the saving of the step, and says that the bar cannot be met when the bar is above the oracle

### Requirement: A decision step has action bands
The outcome of a decision step SHALL be one band of at least three: continue (the cheap or existing path), send to the reviewer (the costly path) and flag (the case goes to the log for a person). The thresholds of the questions SHALL give the band.

#### Scenario: Each band is reachable
- **WHEN** a test gives the step answers below, between and above the fitted thresholds
- **THEN** the step returns the continue band, the reviewer band and the flag band

### Requirement: A decision step runs in shadow before a switch
A decision step SHALL have a setting that is off by default. A step with a shadow mode SHALL, in that mode, log and count its band beside the real result and SHALL change nothing else. The metric SHALL have labels with a bounded set of values, and the documents SHALL state its series count.

#### Scenario: Shadow changes nothing
- **WHEN** a decision step runs in shadow mode with a fake Jev
- **THEN** the real path runs as with the setting off, one log record and one counter increment name the band, and the result of the workflow is equal

### Requirement: A decision step fails open
A decision step SHALL send the case to the existing path when Jev raises an error, times out, leaves a question unanswered, or answers with a confidence below the fitted floor. It SHALL log the cause. A Jev answer SHALL NOT be the only security control of any path.

#### Scenario: Jev fails
- **WHEN** a decision step gets an error from Jev
- **THEN** the existing path runs and one log record names the error

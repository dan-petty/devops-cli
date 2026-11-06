## ADDED Requirements

### Requirement: Plan-recheck names the gate of each refusal
The plan-recheck report SHALL name the gate of each refusal. The gate is `read` for a folder that the plan reader refuses, `openspec` for a finding of `openspec validate`, or the name of one gate of `check_proposal`.

#### Scenario: A refusal carries its gate
- **WHEN** a plan names a file that no commit holds, and `check_proposal` refuses it
- **THEN** the line of the refusal holds the gate name `paths` and the message of the gate.

### Requirement: Plan-recheck compares a branch with the default branch
With the option `--branch <ref>`, plan-recheck SHALL read each change folder of the ref and of the default branch with the plan reader, judge both sets with the same gates, and call no model.

#### Scenario: Both sides are read
- **WHEN** the branch holds one change folder and the default branch holds two
- **THEN** the run reads three change folders with the plan reader and makes no model request.

### Requirement: Plan-recheck lists the refusals of each gate for both sides
With the option `--branch <ref>`, the plan-recheck report SHALL list the refusals of each gate for the branch and for the default branch.

#### Scenario: Each side lists its refusal under the gate
- **WHEN** one gate refuses one change folder on the branch and a different change folder on the default branch
- **THEN** the report lists both refusals under the name of that gate, each with its side.

### Requirement: A refusal that the branch adds is a case to review
With the option `--branch <ref>`, the plan-recheck report SHALL name the folder, the gate and the message of each refusal that the branch adds to the default-branch result, and SHALL mark each one as a case to review.

#### Scenario: A new refusal holds its three facts
- **WHEN** a change folder of the branch makes one gate refuse, and the default-branch result holds no such refusal
- **THEN** the report holds one line with the folder, the gate name, the message and the mark `case to review`.

### Requirement: A folder that the reader refuses does not stop a comparison
With the option `--branch <ref>`, plan-recheck SHALL report a change folder that the plan reader refuses as not read, and SHALL go on with the other folders.

#### Scenario: One folder of the branch does not read
- **WHEN** one change folder of the branch holds no task group and two other change folders read
- **THEN** the report names the unread folder as not read and holds the results of the two other folders.

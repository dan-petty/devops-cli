## ADDED Requirements

### Requirement: A class claim quotes the class source at the staged commit
`check_proposal` SHALL return the class-claim problem when a design decision, a rejected alternative or a `feasibility` line names an internal class under `src/` in a code span that starts with the class name and no other code span of that line holds text of that class at the staged commit.

#### Scenario: A decision that names a class with no quote is refused
- **WHEN** A decision names `StagedTree` in a code span and gives no other code span of that line
- **THEN** `check_proposal` returns the `stage_problem_class_claim` problem for that decision.

#### Scenario: A decision that names a class and quotes it passes
- **WHEN** A decision names `StagedTree.read` and another code span of the line holds `ls-files`
- **THEN** `check_proposal` returns no class-claim problem for that decision.

#### Scenario: A quote that the class does not hold is refused
- **WHEN** A `feasibility` line names `StagedTree` and quotes `file text` in a code span
- **THEN** `check_proposal` returns the class-claim problem for that line.

#### Scenario: A name that no class under src defines is no claim
- **WHEN** A rejected alternative names `ConfigDict` in a code span
- **THEN** `check_proposal` returns no class-claim problem for that alternative.

### Requirement: The class claim reads the class at the staged commit
The check SHALL read each class that a claim names from the staged commit with `git show`, SHALL compare a whitespace-squashed quote of at least three characters with the whitespace-squashed source of that class, and SHALL read the definition line of a class that declares no base.

#### Scenario: The comparison reads the staged commit
- **WHEN** The working tree holds a text that the class source at the staged commit lacks, and a decision quotes it
- **THEN** `check_proposal` returns the class-claim problem for that decision.

#### Scenario: A quote of fewer than three characters is refused
- **WHEN** A decision names `StagedTree` and quotes `ls` in a code span
- **THEN** `check_proposal` returns the class-claim problem for that decision.

#### Scenario: A class that declares no base is read
- **WHEN** A decision names `StagedTree`, which declares no base, and quotes `ls-files`
- **THEN** `check_proposal` returns no class-claim problem for that decision.

### Requirement: The class-claim problem names the class and the plan section
The class-claim problem SHALL come from a `RoadmapMessages` entry that names the class and the plan section, so the planner knows where to add the quote.

#### Scenario: The problem names the class and the section
- **WHEN** The rule refuses a decision that names `StagedTree`
- **THEN** The problem holds `StagedTree` and the word `decision`.

### Requirement: The replay judges a false class claim
The stage replay SHALL hold a case whose plan makes a false claim about an internal class, SHALL record that defect under the `paths` gate, and SHALL hold the note that the case reads no commit when it names no commit.

#### Scenario: The paths gate catches the false claim
- **WHEN** The replay runs the case whose decision claims that `StagedTree` holds file text
- **THEN** The `paths` gate problem holds `StagedTree` and the replay counts the defect as caught.

#### Scenario: The case that reads no commit says so
- **WHEN** The case of the false claim names no base commit and no merge commit
- **THEN** Its notes say that it reads no commit.

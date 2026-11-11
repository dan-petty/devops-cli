## ADDED Requirements

### Requirement: Row 4 compares GitHub with the workflow labels and the file
Row 4 SHALL compare the labels of the repository on GitHub with the workflow labels of the package and the labels of `.github/labels.yml`. With no usable file, it SHALL compare the workflow labels only. When a label is absent, row 4 SHALL be `missing`, and the output SHALL list each absent label.

#### Scenario: A repository with no status/planned
- **WHEN** GitHub holds every workflow label but `status/planned`, and every label of the file
- **THEN** row 4 is `missing` with the reason `1 label(s) missing`, the output lists `status/planned`, and the command exits 1

## MODIFIED Requirements

### Requirement: The labels file is judged
The command SHALL set row 3 to `missing` with the reason when `.github/labels.yml` is absent, is not YAML, or is not a list of labels. Row 4 SHALL then check the workflow labels of the package.

#### Scenario: Each invalid labels file
- **WHEN** each of the three invalid files is on the default branch in turn, and GitHub holds every workflow label
- **THEN** row 3 is `missing` with the matching reason and row 4 is `present`

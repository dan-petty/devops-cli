## MODIFIED Requirements

### Requirement: An evaluation run reads the labels of the checkout
`devops roadmap eval intake` SHALL take the type labels from the package and read `.github/labels.yml` at the root of the checkout it runs in, and SHALL send no GitHub request and no embedding request. With no such file it SHALL stop before any model call with an error that names the file.

#### Scenario: A checkout with no labels file
- **WHEN** the command runs in a directory with no `.github/labels.yml`
- **THEN** it exits 1 with an error that names `.github/labels.yml`, and the model gets no call

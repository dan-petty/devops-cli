## MODIFIED Requirements

### Requirement: The pull request that delivers the code has the type of the issue
The job SHALL set the title of the pull request, for a Staged item and for a Planned item, to the type and the scope of the title of the issue and its summary, shortened so that the part after the colon has at most 60 UTF-16 code units, as `summary_length` counts them, cut at a code point boundary. The job SHALL leave out the scope when `.github/labels.yml` on the default branch declares no label `scope/<scope>`. The job SHALL set the title in the same call that sets the body `Closes #<issue>`.

#### Scenario: A Staged item
- **WHEN** the staging pull request of a bug has the title `docs(openspec): plan #1 keep every comment` and the job finishes the change
- **THEN** the title of the pull request becomes `fix(roadmap): the job drops a comment`, the title of the issue

#### Scenario: A long summary
- **WHEN** the summary of the title of the issue has 80 UTF-16 code units
- **THEN** the title of the pull request keeps the type and the scope, and its summary has at most 60 UTF-16 code units

#### Scenario: A summary of emoji at the limit
- **WHEN** the summary of the title of the issue is 30 emoji of one code point each, which is 60 UTF-16 code units
- **THEN** the title of the pull request keeps the summary unchanged, and its summary has 60 UTF-16 code units

#### Scenario: A summary of emoji over the limit
- **WHEN** the summary of the title of the issue is 40 emoji of one code point each, which is 80 UTF-16 code units
- **THEN** the summary of the title of the pull request has at most 60 UTF-16 code units, holds whole characters only, and has no lone surrogate

#### Scenario: A scope that no label declares
- **WHEN** the title of the issue is `fix(floor): the job drops a comment` and `.github/labels.yml` declares no `scope/floor`
- **THEN** the title of the pull request is `fix: the job drops a comment`

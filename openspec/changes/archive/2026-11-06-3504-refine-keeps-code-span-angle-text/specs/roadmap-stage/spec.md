## ADDED Requirements

### Requirement: A title shows a tag as text
`staging_title` and `delivery_title` SHALL keep each tag of the summary as it is, because a title is plain text. GitHub shows a tag word in a title as text, and the check `Semantic PR title` counts its characters. They SHALL still change the `<` of a comment opener into `&lt;`. They SHALL still put a handle or a link in a code span. The schema SHALL count the summary as the title shows it.

#### Scenario: A word in angle brackets in a title
- **WHEN** `staging_title` receives item 3 and the summary `Reject <section>.<option> keys`, and `delivery_title` receives `fix(config): reject <section>.<option> keys`
- **THEN** the titles are `docs(openspec): plan #3 Reject <section>.<option> keys` and `fix(config): reject <section>.<option> keys`

#### Scenario: A comment opener in a title
- **WHEN** `staging_title` receives item 3 and the summary `Block <!-- hidden`
- **THEN** the title is `docs(openspec): plan #3 Block &lt;!-- hidden`

#### Scenario: A summary of the most characters with a tag
- **WHEN** the model gives a summary of the most characters that the schema accepts, and the summary ends with ` <b>`
- **THEN** the schema accepts the reply, and the title passes the form check

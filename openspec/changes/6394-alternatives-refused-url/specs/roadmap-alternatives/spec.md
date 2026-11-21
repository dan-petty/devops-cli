## ADDED Requirements

### Requirement: A link in a fetched page is not a source
The alternatives job SHALL accept the source URL of a page that `fetch_page` read as a source of the reply. It SHALL refuse a reply for reason `url` when the reply cites a link from the text of that page. It SHALL also refuse a reply that cites a URL that the item names and that no tool read. It SHALL log each refused URL.

#### Scenario: A reply cites a link of a fetched README
- **WHEN** the run searches, fetches the repository page that the search returned, and the reply cites a link from the text of that page
- **THEN** the plan holds no check, its failure has the reason code `url`, and the WARNING line names the link

#### Scenario: A reply cites the page that the run fetched
- **WHEN** the run fetches a page that the item names, and the reply cites that page with a trailing slash
- **THEN** the plan holds one check and no failure with the reason code `url`

#### Scenario: A reply cites a URL of the item that no tool read
- **WHEN** the item body names a page, the run does not fetch it, and the reply cites it
- **THEN** the plan holds no check, and its failure has the reason code `url`

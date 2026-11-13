## ADDED Requirements

### Requirement: The gh pages group reads the site status and checks the local settings

The group `devops gh pages` SHALL hold the commands `status` and `verify` only. The MCP server SHALL expose the Pages tools `gh_pages_status` and `gh_pages_verify` only. No command SHALL request a build from the branch source or read the legacy build list `/pages/builds`.

#### Scenario: The group lists status and verify

- **WHEN** the commands of `devops gh pages` are listed
- **THEN** they are `status` and `verify`

#### Scenario: The MCP server has no build tool

- **WHEN** the tools of the MCP server are listed
- **THEN** the list holds `gh_pages_status` and `gh_pages_verify`, and no `gh_pages_build`

### Requirement: devops gh pages status shows the source branch only for a legacy build

`devops gh pages status` SHALL print the source branch and path only when the build type is `legacy`. For the build type `workflow`, it SHALL print that a GitHub Actions workflow deploys the site. When the API omits the build type, the source branch or the path, the status SHALL hold no value for that field.

#### Scenario: A workflow build names the workflow

- **WHEN** the API gives the build type `workflow` and the source branch `main` with the path `/docs`
- **THEN** the output holds "Build Type: workflow" and "a GitHub Actions workflow deploys the site"
- **AND** the output holds no "Source Branch" line

#### Scenario: A legacy build names the source branch

- **WHEN** the API gives the build type `legacy` and the source branch `main` with the path `/`
- **THEN** the output holds "Source Branch: main (path: /)" and "Build Type: legacy"

#### Scenario: An omitted field has no value

- **WHEN** the API gives a status and a URL, and no build type and no source
- **THEN** the build type, the source branch and the path of the status have no value

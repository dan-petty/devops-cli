## MODIFIED Requirements

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base`, `extended` or `research`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `extended` SHALL hold `research_lookup` and `research_grep`. The toolset `base` SHALL have no GitHub tool, SHALL hold neither ask-mode tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers fifteen tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the ten tools, and none of `references`, `read_issue`, `find_issues`, `research_lookup` and `research_grep`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base`, `extended` and `research`

#### Scenario: The research toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `research`
- **THEN** a plan run offers sixteen tools: every tool of `extended` and `search_web`

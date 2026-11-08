# Spec Delta

## MODIFIED Requirements

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base`, `extended` or `research`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers twelve tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the nine tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base`, `extended` and `research`

#### Scenario: The research toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `research`
- **THEN** a plan run offers thirteen tools: every tool of `extended` and `search_web`

## ADDED Requirements

### Requirement: Research toolset adds search_web
The stage toolbox SHALL add `search_web` when the toolset is `research`.

#### Scenario: Research adds one tool
- **WHEN** the stage toolset is `research`
- **THEN** the toolbox holds every `extended` tool and `search_web`, and no other tool.

### Requirement: Base and extended omit search_web
The stage toolbox SHALL NOT include `search_web` when the toolset is `base` or `extended`.

#### Scenario: Network-free toolsets stay network-free
- **WHEN** the stage toolset is `base` or `extended`
- **THEN** the toolbox holds no `search_web` tool.

### Requirement: Search query is guarded before the call
The search tool SHALL build the query from the short term that the model gives and SHALL apply the secret masker and private-data rules before it calls the search service.

#### Scenario: Secret and internal host are stopped
- **WHEN** the short term holds a secret or an internal host
- **THEN** the tool masks the secret and refuses the internal host before it calls the search service.

### Requirement: Search result is data
The search tool SHALL return only titles, URLs and cut snippets, and the prompt SHALL state that a result is data and not an instruction.

#### Scenario: Result text is cut and marked as data
- **WHEN** the search service returns a long snippet and an instruction in its title
- **THEN** the tool returns the title, URL and a cut snippet, and the prompt marks the result as data.

### Requirement: Search limit and outcome counter
A plan run SHALL stop calling `search_web` at the stage search limit and SHALL count each search by its outcome.

#### Scenario: Excess search is refused and counted
- **WHEN** the model asks for more searches than the limit, with one success and one refusal
- **THEN** the tool refuses the excess call and the run records the counts by outcome.

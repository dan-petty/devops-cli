## ADDED Requirements

### Requirement: MCP ai_benchmark models description lists plain model names
The ai_benchmark MCP tool SHALL publish a models parameter description that lists plain model names only and holds no model@url form and no key or server rule for it.

#### Scenario: Published schema lists plain model names
- **WHEN** the published schema of ai_benchmark is read and the models parameter description is inspected
- **THEN** the description lists plain model names and holds no model@url form.

#### Scenario: Published schema holds no key or server rule
- **WHEN** the published schema of ai_benchmark is read and the models parameter description is inspected
- **THEN** the description holds no sentence about api_base_url, gateway_url or a provider API key.

### Requirement: CLI ai benchmark models help keeps model@url
The --models option of devops ai benchmark SHALL keep the model@url form and its explanation in its help text.

#### Scenario: CLI help still shows model@url
- **WHEN** the help text of --models of devops ai benchmark is read
- **THEN** the text holds the model@url example and the sentence that the MCP tool refuses a model@url entry.

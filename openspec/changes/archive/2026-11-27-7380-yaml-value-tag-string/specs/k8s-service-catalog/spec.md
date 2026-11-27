## ADDED Requirements

### Requirement: The catalog reads a plain equals of a render as a string
`devops k8s catalog` SHALL read a plain scalar `=` of a render as the string `"="`, as Kubernetes reads it. PyYAML resolves such a scalar to the YAML 1.1 tag `tag:yaml.org,2002:value`. The shared safe loader SHALL construct that tag as a string on a subclass of the PyYAML loader, and `yaml.SafeLoader` and `yaml.CSafeLoader` SHALL stay unchanged.

#### Scenario: A chart render holds a CRD enum with a plain equals
- **WHEN** the render of a chart Application holds a CustomResourceDefinition whose enum lists `- '!='`, `- =`, `- =~` and `- '!~'`
- **THEN** `build_catalog` reads the render with no `ConstructorError` and lists the workloads of each Application

#### Scenario: The shared loader reads a plain equals
- **WHEN** `yaml.load_all` with `YAML_SAFE_LOADER` reads two documents, and the second holds the block sequence `- '!='`, `- =`, `- =~` and the flow sequence `[=, a]`
- **THEN** the second object holds the lists `["!=", "=", "=~"]` and `["=", "a"]`

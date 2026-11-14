## ADDED Requirements

### Requirement: A cut tool answer names its cap
A stage planner tool that cuts its answer at a cap SHALL mark the answer with the name of that cap in the metadata of its `ToolReturn`: `lines` for `CONST_ROADMAP_REFINE_TOOL_MAX_LINES`, `chars` for the default character cap, `spec` for `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS`, `log` for `CONST_ROADMAP_STAGE_LOG_MAX_COUNT`, and `map` for `CONST_ROADMAP_STAGE_MAP_MAX_FILES`. An answer that no cap cuts SHALL carry no cut name.

#### Scenario: A long answer names its cap
- **WHEN** a test calls a stage tool whose answer is longer than `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines, and the same tool with a short answer
- **THEN** the long answer holds a cut name in its metadata and the short answer holds none

#### Scenario: A full history names the commit cap
- **WHEN** a test runs `git_log` on a history with one more commit than `CONST_ROADMAP_STAGE_LOG_MAX_COUNT`, and on a history that fits
- **THEN** the first answer names `log` and the second names no cap

#### Scenario: A full map names the file cap
- **WHEN** a test runs `repo_map` on a directory with more files than `CONST_ROADMAP_STAGE_MAP_MAX_FILES`, and on one that fits
- **THEN** the first answer names `map` and the second names no cap

### Requirement: The trace records the cap of a call
The record of a tool call in the run trace SHALL hold the cap that cut its answer, or None when no cap cut it.

#### Scenario: A trace keeps a cut answer
- **WHEN** a test absorbs messages that hold one cut tool answer and one whole tool answer
- **THEN** the first call record names the cap and the second names none

### Requirement: The cut counter is declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_tool_cuts_total` as a counter with the unit `1`, and `docs/TELEMETRY.md` SHALL list it with its kind and unit. The end of a run SHALL add 1 to the counter for each cut answer with the labels tool, row, toolset and cap, and SHALL add nothing for an answer that no cap cut.

#### Scenario: One cut answer adds one count
- **WHEN** a test calls `end_run` with a trace that holds one cut call and one whole call
- **THEN** the counter receives one data point of value 1 with the labels of the cut call, and none for the whole call

#### Scenario: The registry and the document list the counter
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_tool_cuts_total` with the kind Counter and the unit 1

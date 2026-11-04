## ADDED Requirements

### Requirement: The first plan request has fixed caps and leaves a reserve for the tools
The first request of a plan run SHALL cap the context at `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body at `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, and a larger window SHALL NOT give a larger cap. Half of the window for the context, or one quarter for the body, SHALL cap it when that is less. For plain text, the request at the caps SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the limit at which the run offers no tool.

#### Scenario: The context and the body at their caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens, the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, the first request counts at most the limit of 49152 tokens less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`, and the first request offers `read_spec`

#### Scenario: Code at the caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are code, longer than their caps
- **THEN** the first request counts less than the limit of 49152 tokens, and the first request offers `read_spec`

#### Scenario: A large window
- **WHEN** a plan run has a window of 1048576 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens

#### Scenario: A small window
- **WHEN** a plan run has a window of 8192 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts 4096 tokens and the body counts 2048 tokens

### Requirement: The context and the largest spec answer stay under half of the window
The context of the first plan request and the longest answer of `read_spec` SHALL together stay under half of the context window of the `analysis` task.

#### Scenario: The longest spec answer
- **WHEN** a test adds an answer of `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS` characters to a context of `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens
- **THEN** the sum is under 32768 tokens

### Requirement: The trace of a run records the tools that each request offered
`RunTrace` SHALL hold, for each model request of a run, the names of the function tools that the request offered, and an empty entry for a request that offered none. The combined trace of several runs SHALL hold the entries of every run in order.

#### Scenario: A run that loses its tools
- **WHEN** a scripted plan run reads a big file until the window limit takes the tools, and the model then gives its plan
- **THEN** the trace holds the tool names of the first request and an empty entry for the last request, and the entries equal the tools that the model saw

#### Scenario: Two runs
- **WHEN** `RunTrace.combined` gets two traces that hold one and two entries
- **THEN** the result holds the three entries in order

### Requirement: The comment states why a run made no tool call
The comment of a staged item whose plan runs made no tool call SHALL state the reason. When no request offered a tool, the comment SHALL say that each request reached the tool-removal limit of the context window. When some request offered tools, the comment SHALL say on how many of the requests tools were offered, and that the model called none.

#### Scenario: A run that offered no tool
- **WHEN** a plan run has a window so small that the first request offers no tool, and the model gives its plan
- **THEN** the comment says that the run offered no tool because each request reached the tool-removal limit of the context window

#### Scenario: A run that offered tools
- **WHEN** a plan run offers tools in its one request and the model gives its plan with no tool call
- **THEN** the comment says that the run offered tools on 1 of 1 request(s) and the model called none

### Requirement: The window of the analysis task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `analysis` and the file that sets it, and the `max_input_tokens` of the model of that task and the file that sets it. The stated values SHALL equal the values in `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a test reads the two files and the page
- **THEN** the page states 65,536 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and `k8s/llm/gateway/config.yaml`, as the files hold them

### Requirement: The refine investigation request is measured against the tool-removal limit
A test SHALL build the first request of a refine investigation at a window of 65536 tokens, count its tokens as the run hook counts them, print the count with the limit of 49152 tokens, and assert that the request of a large item stays under the limit. Refine SHALL NOT change.

#### Scenario: A large item
- **WHEN** refine investigates an item with a body of 8192 tokens and three replies of 1000 tokens
- **THEN** the test prints the count and the limit, and the count is under 49152 tokens

## MODIFIED Requirements

### Requirement: The map and the spec tools give short answers
`repo_map` SHALL give one line for each of at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files, with the path and the names of the top-level symbols, cut to 180 characters, and a last line that says so when the directory holds more files. `read_spec` SHALL read the specs from the JSON of `openspec list --specs` and `openspec show --type spec`. For one capability it SHALL answer with a line `Purpose:` and then the requirement names. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

#### Scenario: A capability
- **WHEN** `read_spec` gets a capability and no requirement name
- **THEN** it answers with a first line `Purpose:` and the purpose, and then the requirement names

#### Scenario: A capability with no requirement
- **WHEN** `read_spec` gets a capability that holds a purpose and no requirement
- **THEN** it answers with the line `Purpose:` and the purpose

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model every capability under `openspec/specs/`. A plan run that has the tool `read_spec` SHALL get the names of the capabilities in the first request and SHALL read the purpose and the requirement names of one capability with `read_spec`. A call with no tool SHALL get the purpose and the requirement names of every capability in the input.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal that is planned with one call and no tool
- **THEN** the input holds the purpose and the requirement names of each capability

#### Scenario: The input of a run with read_spec
- **WHEN** The stage job builds the first request of a plan run that has `read_spec`, for a checkout with many capabilities
- **THEN** the `capabilities` key holds the name of every capability in order, the request holds no purpose and no requirement name, and the run offers `read_spec`

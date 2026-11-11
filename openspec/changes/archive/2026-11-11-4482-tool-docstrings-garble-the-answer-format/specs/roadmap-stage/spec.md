## ADDED Requirements

### Requirement: Each read tool description shows its answer format whole
The description that the stage planner and the refine investigation send for each read tool SHALL hold the answer format of the tool whole, such as `path:line:content` for `search_code` and `callers` and `line: signature` for `file_symbols`. No description SHALL hold a `<returns>` part that the docstring parser makes.

#### Scenario: The model reads the search tool
- **WHEN** the stage planner or the refine investigation builds the definition of `search_code`
- **THEN** its description holds `path:line:content` whole and has no `<returns>` part

#### Scenario: The model reads the symbol tool
- **WHEN** the stage planner builds the definition of `file_symbols`
- **THEN** its description holds `line: signature` whole and has no `<returns>` part

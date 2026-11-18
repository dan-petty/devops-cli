## MODIFIED Requirements

### Requirement: The inputs of a step are fixed
The user message SHALL hold, in order: the `AGENTS.md` of the checkout and its routed sections; the title, problem and criteria of the item; the `proposal.md`, `design.md` and `tasks.md` of the change; the comments of the item that the run gives; the group; its named files, packed; and, except for a fix step, the path of `tasks.md` under "The tasks file". It SHALL hold nothing else. The change is the one folder `openspec/changes/<N>-*/`, else the step SHALL raise `RoadmapImplementError`.

#### Scenario: The first request
- **WHEN** the step runs group 1 of a change whose group 1 names `src/sample.py` and `tests/test_sample.py`, which does not exist yet
- **THEN** the first request holds the item title, the two sections of the issue, the three documents, the text of group 1, the packed `src/sample.py`, the path `openspec/changes/1-sample-change/tasks.md` and the text of `AGENTS.md` under the heading "Rules of the repository (AGENTS.md)", and it holds no text of another file

#### Scenario: A fix step
- **WHEN** a fix step builds its inputs
- **THEN** the message holds no section "The tasks file", and it holds `AGENTS.md`

#### Scenario: A missing change
- **WHEN** the checkout holds no folder `openspec/changes/7-*/`
- **THEN** the step raises `RoadmapImplementError` that names the pattern

## ADDED Requirements

### Requirement: A step reads every trusted comment of the item
The run SHALL read the comments of the item once, and each step, a fix step too, SHALL get every comment that a person with write access or the Service App wrote, oldest first, each with its number, its author and its time: the comments of persons and the comments of the roadmap jobs. A comment of any other account SHALL NOT be in the inputs. The agent SHALL have the tool `read_comment`, which reads any comment of the item whole, page by page, or lists every comment.

#### Scenario: A decision after the plan merged
- **WHEN** an item has a note before its plan merged, a decision of a person and a stop of the implement job after it, and a comment of an account with no write access
- **THEN** the inputs hold the note, the decision and the stop, the heading of the decision says that it came after the plan merged, and the inputs hold no text of the other account

#### Scenario: A comment of the index
- **WHEN** the agent calls `read_comment` with the number of a listed comment of 39 lines
- **THEN** the answer holds line 1 and line 39

### Requirement: The comments of a step say when the plan merged
The section of the comments SHALL say when the plan merged: the author time of the newest commit of the checkout that added the `tasks.md` of the change, also after the run archived it. It SHALL hold the line "Comments of persons on the item after its plan merged; a decision here overrides the plan text.", and each whole comment SHALL say whether it came before or after the plan merged.

#### Scenario: The plan time of an archived change
- **WHEN** a fix step reads a change that the run archived a day after its plan merged
- **THEN** the plan time is the time that the plan merged

### Requirement: The comments never take a step over the window
The comments SHALL take at most `CONST_ROADMAP_IMPLEMENT_COMMENTS_MAX_TOKENS` tokens and at most the room that the other inputs leave under the limit of the window. The newest comments SHALL come whole while they fit, and each older comment SHALL get a line of an index while it fits. No comment SHALL be cut. When no section fits, one line SHALL count the comments, and those after the plan merged, and name `read_comment`.

#### Scenario: Comments that do not fit
- **WHEN** the window leaves 400 tokens for the comments of an item with a comment of 6,000 words and a later decision
- **THEN** the inputs stay under the limit, hold the decision whole, list the long comment in the index, and hold no word of its end

#### Scenario: No section fits
- **WHEN** the window leaves 60 tokens for two comments, one of them after the plan merged
- **THEN** the inputs hold the line "This item has 2 comments that did not fit the input (1 after the plan merged); read them with `read_comment`." and no section of the comments

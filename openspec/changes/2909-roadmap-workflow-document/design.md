# Design

## Context

See proposal.md for the motivation (#2909). The document names the workflow that W2 (#2920) and W3 (#2910) built, and marks as planned what the other items of tracker #2908 will build.

## Goals / Non-Goals

**Goals:**
- One page names the eight steps, the actor of each, the states, the labels, the record keys and the three gates.
- A test holds the page in sync with the labels file and the code.
- A later item of the tracker changes one line of the page.

**Non-Goals:**
- Change a command, a label or the Service. The change builds none of the planned items.

## Decisions

### 1. One table of the steps, one table of the transitions
- **Decision**: The steps table has the columns step, state after it, Service job, agentic coder, person and gate. The transition tables have the columns from state, event, to state and actor.
- **Alternative considered**: One table that mixes steps and transitions.
  - *Rejected*: A step holds many transitions (a stop, a retry, a claim). One table would repeat the step in each row and hide the order.

### 2. All planned work in one section
- **Decision**: The section "Planned changes" holds each planned item with its issue number. The rest of the page describes the built workflow and points to that section.
- **Alternative considered**: Mark planned text where it belongs, with the issue number.
  - *Rejected*: When an item merges, a person must find each mark. With one section, the item changes one line and the page stays true.

### 3. The test reads code spans, tables and fences from markdown-it tokens
- **Decision**: A label or a record key counts as named when a code span holds exactly that text. The transition table is a table token whose header row has the four columns. The diagram is a fence with the info string `mermaid`.
- **Alternative considered**: A regular expression over the raw text.
  - *Rejected*: AGENTS.md rule 3 and the project rule against hand-rolled parsing. A regular expression also matches a label in a quote or a link, which is not a statement of the workflow.

### 4. The test checks the code, not only the labels file
- **Decision**: The test takes the Status and Owner values from `CONST_ROADMAP_STATUS_VALUES` and `CONST_ROADMAP_OWNER_VALUES`, and the record keys from the four key enums of `roadmap/store.py`. It also checks that the labels file and the code agree.
- **Alternative considered**: The labels file alone.
  - *Rejected*: The issue asks for the states of the code. A state added to the code without a label would pass.

### 5. The new document is routed by replacing words
- **Decision**: The row "move a pull request from draft to merge" of the `AGENTS.md` table gets the document as one more link, and its words get shorter by the same count.
- **Alternative considered**: A new row.
  - *Rejected*: The file is at its cap.

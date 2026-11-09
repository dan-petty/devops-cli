## MODIFIED Requirements

### Requirement: A plan run keeps its messages inside the context window
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `stage` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free. The run SHALL take the tokens of its messages from the usage of the last reply of the model, which is its input and its output, plus the count of the text that came after that reply. With no reply that reports its input, the run SHALL count the text that the model reads and not the JSON form of the messages. The run SHALL use no fixed factor.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

#### Scenario: The count follows the reported input
- **WHEN** the last reply of a run reports an input of 105,412 tokens and the window is 200000
- **THEN** the count of the messages is within 10 percent of 105,412 tokens and the next request offers its tools

#### Scenario: The reported input has no room for a reply
- **WHEN** the last reply reports an input of 149,900 tokens and the window is 200000
- **THEN** the next request offers no tool

#### Scenario: The text after the last reply counts
- **WHEN** the last reply reports 140,000 tokens and the answer after it holds more than 10,000 tokens of text
- **THEN** the next request offers no tool

#### Scenario: The first request
- **WHEN** the run has no reply yet
- **THEN** its count is the count of the instructions and the user prompt, within 2 percent

#### Scenario: A reply that reports no input
- **WHEN** a provider omits the input tokens of its replies
- **THEN** the count of the messages is the count of their text, within 2 percent

#### Scenario: A call to a tool that is not offered
- **WHEN** the model calls `read_file` while only `final_result` is offered
- **THEN** the return names `final_result` as the tool that is available

## MODIFIED Requirements

### Requirement: Refine writes the code in the model's text as it is
Refine SHALL write a link, a handle or a reference in a code block of the model's text as it is, and in a code span as it is when the text shows no backtick as text. A code span that refine adds SHALL close on its own backticks only, also where GitHub takes a later code span of a length that it closed before as text. Refine SHALL put each point of a next step on one line before it sanitizes the point.

#### Scenario: A link, a handle or a reference in code
- **WHEN** the model's text is ``Run `curl www.example.com` here``, ``Run `see other/repo#1 now` here``, ``Ask `ping @alice now` ``, a fenced code block or an indented code block that holds a `www.` link
- **THEN** refine writes the text as it is

#### Scenario: A link next to the model's backticks
- **WHEN** the model's text is ``A `b www.example.com c``, with one backtick that opens no code span
- **THEN** refine writes ```A `b ``www.example.com`` c```, whose added code span closes on its own two backticks

#### Scenario: A text with a backtick that opens no code span
- **WHEN** the model's text is ```A `` `x` `see www.example.com` B```, in which GitHub shows `see www.example.com` as text
- **THEN** refine writes ````A `` `x` `see ```www.example.com``` ` B````, which GitHub shows with `www.example.com` as code

#### Scenario: A comment point with a code block
- **WHEN** a split-off of the model is `Read this:`, a blank line, and `www.example.com` indented by four spaces
- **THEN** the next step holds the point ``Read this: `www.example.com` ``

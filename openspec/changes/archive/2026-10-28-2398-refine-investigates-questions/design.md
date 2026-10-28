# Design

## Two phases: propose, then investigate what stays open

The proposal request stays one `chat_structured` call through `LLMClient`, as today. Its errors, retries, spend records and cache stay as they are, with the failure handling of #1363 and #1526. Validation then finds what stays open: a fact or a decision with no verified source, and a numbered body question that no answer names. Only when something is open does refine run the investigation: one pydantic-ai `Agent` for the item, with the read-only tools and `RefinementProposal` as its output type, which pydantic-ai's default `ToolOutput` asks for as the call of an output tool. The request holds the issue, the replies, the body questions, the first proposal and the questions that stay open, each decision with no verified source among them. It holds no repository context: the tools read the code. The agent returns the whole revised proposal, and refine validates it as it validated the first. So an item with nothing open costs one request, as today, and the cost of an investigation goes only to an item that would wait on a person.

Rejected:

- **One agent run for the whole proposal.** It would replace `chat_structured` for every item. Then every item pays for a tool loop, and the error handling of #1363 and #1526, with its tests at the HTTP edge, moves to pydantic-ai's errors.
- **A research plan before the proposal, with more queries.** This is the old design. Before the model knows its questions, it cannot choose the searches, and it cannot read code. Most open facts are about the repository (#2234 asks four, all about its own code).
- **`PydanticAgent`** (`src/devops_cli/ai/agents/agent.py`). It finds a tool call by parsing the model's text (`_detect_tool_intent`), adds a RAG step that swallows every exception, and keeps memory. `LLMClient` has no native tool calls.
- **`NativeOutput`.** The gateway sends the schema to Ollama as `format`, which constrains every reply to the schema, so the model could call no tool.
- **`PromptedOutput`.** Its instructions tell the model to always answer with a JSON object. Against `qwen3.8:27b` through the gateway, the model then wrote each tool call as JSON text (`{"name": "list_files", "arguments": {...}}`), pydantic-ai read that text as the answer, and the run failed after its output retries. The same gateway returns native `tool_calls` for a plain request with one tool, and with `ToolOutput` the model called its tools natively and settled two of the four open facts of #2234.

## The tools

All tools read the commit refine pinned (`inspect_checkout`), so a source the agent cites validates against the same tree. Each tool answers a failure as text and raises nothing, because pydantic-ai passes a tool's exception through the run and would stop the whole refine round: git runs with bytes output, which the tool decodes as UTF-8 with replacement; a file that holds a NUL byte is binary; an argument that holds a NUL byte runs nothing; a command that runs out of its 15 s gets an answer that says so.

- `search_code(text)`: `git grep -n -I -F -i` for the text. The output lines start with the repository path and line, which the agent can cite as `path:line`. At most `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines.
- `list_files(directory)`: `git ls-tree --name-only` of the directory, at most `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` names.
- `read_file(path, start_line, end_line)`: the lines of the file with their numbers, at most `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines from `start_line`. A path outside the repository, a path that the commit does not hold and a binary file each get a plain answer that says so.
- `search_web(query)`: present only when the repository is public and a Firecrawl key is set. It calls `firecrawl_search` (`src/devops_cli/ai/common_tools.py`), which posts `{query, limit}` to Firecrawl's `/v2/search` through the egress factory at level `PUBLIC`, and answers each result's title, URL and description. It asks for no page scrape, which costs a credit for each result. Each `http` or `https` URL it returns joins the allowed URLs. At most `CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES` searches for each item.

A tool answer is text, cut to `CONST_ROADMAP_REFINE_TOOL_MAX_CHARS`. `UsageLimits(request_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS, tool_calls_limit=CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS)` caps a run, and the model gets `CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES` retries for a tool call and for its answer. pydantic-ai's `PrepareTools` capability removes the function tools when fewer than `CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS` tool calls, or only one request, are left, so the model's next reply is the proposal and the run ends inside its budget. Without it, `qwen3.8:27b` used the 12 calls of the first budget, two in each turn, and the run stopped before its answer.

The run passes an event stream handler that reads the events, so pydantic-ai streams each model request (`agent/abstract.py`). From a workstation, the gateway URL goes through the Cloudflare tunnel, which cuts a reply that does not stream after 125 s; `LLMClient` streams for the same reason (#2379).

The CLI sets `PYDANTIC_AI_NO_BANNER` in its entry point, beside `PYDANTIC_DISABLE_PLUGINS`, so pydantic-ai prints no first-run banner into the CLI's output.

Rejected: **the Firecrawl SDK** (`firecrawl`). It calls `requests.post` and takes no session or client, so it would bypass the egress factory (SECURITY.md item 2).

## Errors of the investigation

The investigation turns a failed model call into refine's classes, so `plan_refine` handles it as it handles the proposal's:

- `ModelHTTPError` with status 401 or 403 is `AICredentialsError`, which stops the run.
- Any other `ModelAPIError` is `AIClientError`. It says nothing about the item and records nothing, so the next round tries the item again.

A run that ends with no proposal returns `InvestigationStopped` with the class of pydantic-ai's error: `UsageLimitExceeded` (a turn asked for more calls than the budget holds) or `UnexpectedModelBehavior` (the model's answer or tool arguments broke their schema past the retries, or it called a tool that the budget removed). Neither says that the first proposal is wrong, so refine keeps it: the item waits on a person with its open questions, and refine logs a warning that names the item and the class.

Rejected: **a stopped run as `StructuredOutputValidationError`.** Apply then records the body as failed (#1526), and the valid first proposal is lost for a fault of the investigation.

The run's usage goes to the spend ledger with `track_request_spend`, stage `analysis`, as one record for the run, summed from the replies that `capture_run_messages` holds, so a stopped or failed run is recorded too. A model that the bridge sends to a gateway carries the gateway's URL in `served_by`, and its record names the provider `gateway` and the gateway's host, as `LLMClient`'s records do. pydantic-ai gives no reply header, so the record cannot name the backend that the gateway chose: the ledger prices it as the gateway's host, which is local for the `analysis` route on Ollama.

## The model of the investigation

`get_task_model("analysis")` in `src/devops_cli/ai/client/factory.py` gives the pydantic-ai model of a task: the client override when it is a pydantic-ai `Model` (#1001, ADR 0007), else `resolve_pydantic_ai_model` with the task's model. The tests install one `ModelFake` that serves both phases. It resolves each request's parameters with `prepare_request`, as pydantic-ai's own test models do, and answers a request that takes its answer only through an output tool with the call of that tool, streamed or not.

## Questions and decisions

`QuestionAnswer` gets `kind` `fact`, `decision` or `person`, `options` (a list of `DesignOption`: `option`, `chosen`, `reason`) and `body_question` (the number of the body question it answers, or null). The marks: a decision whose answer quotes an owner decision of the body shows "(owner decision)"; one with a verified source shows "(best practice)"; any other shows "(proposed)". A mark that the model copied from an earlier section goes first, so each answer ends with exactly the mark it earns, and `needs_investigation` reads that last mark. A `person` question goes to the open questions with "(a person decides)". The section renders the chosen option and each rejected option with its reason under the answer.

Rejected: **a decision needs a source to pass.** Without web search, many decisions can cite only the repository, and the plan is a proposal that the builder checks again (AGENTS.md rule 2). A decision with no source stays "(proposed)" and does not stop Ready, as before.

## Body questions

`body_questions(body)` parses the body outside refine's own section as CommonMark with markdown-it-py. The section is the tokens under the first heading titled "Key questions", up to the next heading of the same or a higher level. Each top-level list item whose first paragraph holds a question mark is a question. Text other than emphasis after its last question mark answers it in place, and so does any block after that paragraph inside the item: a nested list, an indented paragraph or a code block. A wrapped question stays one question, and a paragraph, a code block or a list item with no question mark is not one. The request carries the unanswered questions as `body_questions`, numbered from 1. A number that no answer names is an open question.

Rejected:

- **Keep the substring match with better normalization.** The match fails each time the model words a question in its own way, and no normalization can tell a statement bullet from a question.
- **Line rules for bullets and indentation.** They break on a question that wraps, a paragraph after the list, a sub-heading and a `#` line in a code block, which the review found; a CommonMark parser handles each of them.

## Web search state

`RefinePlan.web_search_off` holds the reason when the round had no web search: the repository is private, or `firecrawl.api_key` is not set. The report prints it once under its title.

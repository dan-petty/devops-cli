# Design

## Decisions

- **Read each rule from the code that enforces it.** The keys come from `model_fields` of the reply models, the limits from `SUMMARY_MAX_CHARS`, `BODY_MAX_CHARS` and `PURPOSE_MIN_CHARS`, the forms of `verify` from `form_problems`, the closing words from `closing_keyword_in` and the no-spec paths from the problem text of `check_proposal`. A new key or limit then breaks the test and names the prompt line to change. The reason: the code is what the job enforces, so it is the right side of a disagreement.
- **Hold a rule that has no machine form by a shared phrase.** The test keeps a short list of phrases, such as the form `! git grep -n <name> src/ tests/` and the sentence that names the kinds of change that need no test, which the prompt and a document both say word for word. When one side changes the phrase, the test sends the author to the other side. The reason: a phrase is a small, cheap check, and a copy of the whole document would cost tokens in a small window.
- **Check each `uv run devops` example of the prompt against the command tree.** `resolve_devops_argv` parses the example without running it, so a renamed command breaks the test. The reason: a stale example sends the planner to a command that does not exist, and the form check would still accept it.
- **Keep the 40 of the summary.** The title is `docs(openspec): plan #<number> <summary>` and the whole part after the colon has at most 60 characters. A five-digit number leaves 48. The test holds the prompt limit at or under that room, so the 40 is a safe choice and not a copy of 60.
- **Do not generate a line of the prompt.** A generated line needs a render step in `src/devops_cli/roadmap/stage.py` and in the split job, which three open pull requests also change, and `load_task_prompt` has no placeholder. The test gives the same guarantee for the seven rules. If a later rule has a long list that changes often, generate that line then.
- **Do not give the planner `AGENTS.md` and the routed documents.** The prompt is 2,602 tokens; `AGENTS.md`, `CONTRIBUTING.md`, `docs/TESTING.md` and `openspec/config.yaml` are 20,793 tokens together (`count_tokens`), eight times the prompt, and the planner also gets the context, the probes and the capabilities. The implement step already reads the routed sections of those documents. The tests keep the small copy right at a cost of zero tokens in the window. This answers the open question of the issue: not now.
- **Fix the prompt when the code is right.** The closing keywords are the nine words of GitHub, and `closing_keyword_in` refuses all nine. The prompt names six, so the prompt changes.

## Rejected alternatives

- **Run the planner and compare its answer**: needs a model call. The tests double model edges, and the golden set of `devops roadmap eval` already measures answers.
- **Copy the rules of the documents into the prompt by a script**: moves tokens into the window of the planner for a rule it does not need, and adds a build step. The shared phrases and the machine forms are enough.
- **Name the no-spec paths as a public constant in `stage_change.py`**: needs an edit of a file that three other pull requests change. The problem text of `check_proposal` already carries the list.

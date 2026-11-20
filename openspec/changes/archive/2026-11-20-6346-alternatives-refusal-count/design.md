# Design

## Decisions

- The count is the number of answered searches, `len(AlternativesTools.searches)`. The module records a `Search` only when a provider answers it, so a failed or refused search does not count. This is the count that a written check logs.
- The count is a field of `CheckFailure`. The failure is the object that reaches `AlternativesWriter._log`, and the tools object of the run is gone at that point.
- Each failure that `_check_one` makes after the agent run starts sets the field, so the result line of a stopped run (`refused`) and of a failed model call (`failed`) is also true. A skip-class failure makes no search and keeps 0.
- `validate_reply` logs the WARNING at the refusal point, where both the reply and the URLs that the tools returned are known. It logs one line for each URL that no tool returned, in the order of the reply, with each URL once. The refusal text names only the first URL, so the log line is the record of the others.
- The run's returns are a field of `CheckFailure` for the same reason. `_OutputChecker.returns` already gives them to a written check, so each failure takes the same count.
- The log line holds the whole URL, query included: #6394 needs it to find the cause. The Service log path applies `mask_secrets` to each line (SECURITY.md rule 1), and the log stays in the cluster, so rule 8 of SECURITY.md, which covers committed files and public evidence, does not apply.
- The refusal text and the reason code do not change, so the retry message, the job record and the decision point `alternatives.reply_fixable` do not change.

## Rejected alternatives

- Count the calls of `search_web` (`search_calls`): it counts searches that no provider answered and refused queries, which `Search` leaves out by design (#4044).
- Count the search results: it counts URLs, not searches.
- Read the count again at log time: the tools object is local to `_check_one`, and the writer logs after the check returns.
- Log the whole reply: it can hold the full text of the model and adds noise. The URL is the fact that #6394 needs.
- Log the URL with no query and with private hosts masked: #6394 needs the full URL to compare it with the URLs that the tools returned, and the Service log already masks secrets.
- Fix the cause of the refusal in this change: Loki holds the URL of one refusal in 7 days, and the four re-check refusals of #6346 do not explain #6324. #6394 fixes the cause when the new log lines show it.

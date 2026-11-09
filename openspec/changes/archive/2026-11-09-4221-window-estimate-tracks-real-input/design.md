# Design

## Decisions

- `tokens_of` finds the last `ModelResponse` of the messages. When its usage holds `input_tokens`, the estimate is `input_tokens + output_tokens` of that reply plus `count_tokens` of the text parts of the messages after it. The reply and the messages before it are already inside `input_tokens`, and the output of the reply is part of the next input.
- With no reply, or with a reply whose `input_tokens` is 0 (a provider that omits the usage, and every streamed `FunctionModel`), the estimate is `count_tokens` of the text parts of all messages. The text parts are the instructions, the user prompts, the tool calls (their JSON arguments), the tool answers, the retry prompts and the text of the replies.
- `tool_stop` and `CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE` stay: the room for the reply is the same.
- The cached tokens of a provider are inside `input_tokens`, so the estimate needs no extra step for them.
- The tests build the messages by hand, because a streamed `FunctionModel` cannot set the usage of its replies.

## Rejected alternatives

- A fixed factor (divide the count by 1.4). The factor depends on the model and on the text, and the issue forbids it. A measured factor of 1.16 to 1.2 for the JSON form was found on code, against 1.4 on the live run.
- A call to the token-count endpoint of the provider before each request. It adds a network request for each model request, and the usage of the last reply already holds the number.
- Keep the JSON dump and only raise `CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE`. This moves the limit for every window and does not make the count follow the real input.
- Change the retry of an unknown tool name (criterion 3 of the issue). The evidence in the proposal shows that the output retry is not used, so there is nothing to change.

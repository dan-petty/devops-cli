## MODIFIED Requirements

### Requirement: An error of the generation inside a stream is sent again
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the step SHALL send the request again, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. The failure has class `parser`, which is deterministic for one conversation. So the first such failure of a step SHALL send the request with one more part in its last request, a message that asks for a smaller edit, and the next such failure of the step, also after a good reply, SHALL end the turn with no send. A send that gets a reply SHALL give the next failed request its own resends. The limits SHALL count the failed requests too. After the last send, the step SHALL stop with the reason of a failed model call and the class `parser`. The `wip:` commits of the step SHALL stay in the branch.

#### Scenario: Two separate failures
- **WHEN** a model request fails with a 400 inside a stream, a good reply follows, and a later request fails the same way
- **THEN** the step stops with the class `parser`, and the later request is not sent again

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the messages of the first and one more part at its end, the message that asks for a smaller edit

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops with the class `parser`, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests, the last one with the smaller-edit message

#### Scenario: The work of the group stays
- **WHEN** the agent ticks the first task of a group and the verification of it passes, then two requests fail with a 400 inside a stream
- **THEN** the step stops with the class `parser`, and the branch holds the `wip:` commit of the first task

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: The failed send counts in the limit
- **WHEN** the replies and the failed send reach `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`
- **THEN** the model gets no more than that many requests, and the step stops with the reason of the request limit

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for a failed static check fails once with a 400 inside a stream
- **THEN** the request is sent again with the message that asks for a smaller edit, and the extra turn ends with the check passing

# Design

## Decisions

- **End at a whole line.**: A half line shows a wrong value to the model, such as a cut path or a cut number.
- **Keep the text of the notice.**: The prompts and the tests already name `(more lines are left out)`, and one notice for both limits is enough for the model.
- **Cut a single long line.**: A minified file has one huge line. The answer must still stay under the limit.

## Rejected alternatives

- **Raise the character limit.**: 17 of 79 answers of the live run reached it, but 337,000 characters of answers are already 105,000 of the 190,000 tokens of the last request. A higher limit fills the window sooner.

# Design

## Decisions

- **Name the server where the output is built, in `commands/ai.py`**: `prewarm` and `preload` call one helper that maps each result key with `server_label`. The client keeps the URL as its key, because the URL is the identity inside the process. A test double of the client also returns URL keys, so the render step is the one place that every output path crosses.
- **Merge nodes with the same label**: Two URLs can share a host and port (a different path or user name). The helper keeps one node and sets it to ok only when every URL of it is ok, so a failure never hides.
- **Bound the label with a character class and a length**: `bounded_label` replaces each character outside `A-Za-z0-9._:/-` with `_` and cuts the text to 128 characters. Model names stay readable in dashboards.

## Rejected alternatives

- **Key the result by label in `ollama.py`**: The client results are also used with URL keys in the callers of `preload_models`, and the test double returns URL keys. A change there would leave the output unfixed for those results.
- **The character set `a-zA-Z0-9._-` of the issue**: It turns `gemma4:26b` into `gemma4_26b`, which breaks the existing counter test and the dashboards that name the model with its tag.
- **A fixed list of model names**: Each new model needs an edit of the list.
- **Hash the model**: A person cannot read a hash in a dashboard.

# Design

## Decisions

- **Repair in the job, not in the problem for the model.**: The omitted text is known, a scenario cannot be dropped on purpose, and the repair saves the one return that the model gets.
- **Render the block again from the reply and append the omitted scenarios.**: The renderer of the job writes the block, so no parser reads the delta file. The reply keeps its own text and order.
- **Match a scenario by name, without the white space at its ends.**: OpenSpec compares names, as its message shows. A reply that rewords a scenario under the same name keeps its own text.
- **Run the repair after the gates and before the validation.**: The gates judge the reply of the model. A restored scenario is old text that the gates have no reason to judge, and the files that are validated are the files that are written.
- **Copy the raw text of the base scenario.**: A base scenario can hold lines that the reply form cannot hold, such as `AND`.

## Rejected alternatives

- **Put the omitted text in the problem that goes back to the model.**: The model can copy it wrongly, and it has one return.
- **Add the base scenarios to the reply before the gates.**: A restored scenario that names code would be judged by the scenario check (#3321) as if the model had written it.
- **Edit the delta file with a text search.**: It needs a parser of the delta that the renderer makes already.

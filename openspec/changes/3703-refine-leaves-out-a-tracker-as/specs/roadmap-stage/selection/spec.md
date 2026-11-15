## MODIFIED Requirements

### Requirement: The job leaves out a tracker
The job SHALL leave out an item that has sub-issues or the label `type/epic`, and the plan SHALL give the reason. Its sub-issues deliver it, so it gets no plan of its own. The job SHALL read the test from `Item.is_tracker` on the model, and the refine job SHALL read the same property, so the two jobs give one answer for one item.

#### Scenario: A tracker under the default filter
- **WHEN** the roadmap holds a Ready item with the label `type/epic`, a Ready item with two sub-issues and a Ready plain bug, and the command runs with no filter
- **THEN** the plan stages the plain bug only, and it names the tracker reason for the other two

#### Scenario: The two jobs read one tracker test
- **WHEN** an item has two sub-issues or the label type/epic
- **THEN** the tracker test on the model is true, and the stage job leaves the item out with the tracker reason

# Design

## Decisions

- A fact goes in the comment only when the labels of the item cannot show it. The labels show the type, the scope, Status, Priority, Value and Effort, and the issue shows the milestone.
- The undeclared scope line stays. The labels show no scope, and only the comment names the label to add to `.github/labels.yml`, as `roadmap-intake-title-labels` requires.
- The Priority line stays for P1-High, P3-Low and P0-Critical, and for each P0 decision on evidence, also when the Priority stays P2-Medium. P2-Medium is the usual Priority (366 of 433 open items), so its reason tells a reader nothing new. A refused P0 tells a person that they can set P0.
- The Priority line keeps its value, because a person can change the label later, and the reason then still names the Priority that intake set.
- When no line is left, intake posts no comment and reads no comments of the issue. A later run of a stopped candidate decides the comment again from the reply of the model, as before.

## Rejected alternatives

- Keep the Value and Effort reasons of the model. No code reads them, the labels show their values, and with the Type and Scope lines they are 4 of the 6 lines of most comments.
- Remove the type, Value and Effort reasons from the reply schema of the model. That changes the model contract and the Jev mapping, and the reasons can help the model to calibrate. It is a separate change.
- Write the comment only for a related item or a possible original. A refused P0 and an undeclared scope then have no record that a person can see.

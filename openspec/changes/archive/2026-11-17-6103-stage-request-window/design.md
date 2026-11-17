# Design

## Decisions

- Lower the context cap, because the tools read repository context on demand, and the body of the item is the main input of a plan.

## Rejected alternatives

- Shorten the stage prompt: a prompt change needs live eval scores before and after, and the text that #6091 added is the rule of the owner of 2026-11-16.
- Lower the tool reserve: it is the room for the answers of the tools, and a smaller reserve gives a run fewer reads.

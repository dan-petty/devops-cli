# Design

## Decisions

- **Record the matching paths of each negative-search literal as a mapping that check_proposal takes as a keyword with a default of no record.**: It follows the probes input: the job records it once, the replay reads it from its case, and a caller with no checkout still gets the created-module check.
- **Read the literal and the relative paths with one parser in the form gate, which reuses the option list of the shell policy.**: A second git grep parser would drift from the form check that already refuses pipes, redirects and unsupported options.
- **Compare the literal with the import path of each created source path under src/devops_cli/.**: It catches the package move of #3378 without reading the content of a file that the plan creates.
- **Ask the planner to call search_code with the literal and to quote the hit count in feasibility.**: The planner can correct the plan before the gate refuses it, and the quote ties the plan to the staged commit.
- **Hold the case of #3378 in tests/roadmap/test_roadmap_stage_negative_search.py, beside the other stage tests.**: The replay then runs the real plan and its recorded evidence offline, with no git call and no network.

## Rejected alternatives

- **Run git grep inside check_proposal.**: The replay calls no git, and plan_check judges a change folder with no checkout of the staged commit.
- **Record only the total hit count of a literal.**: A total cannot show whether a hit sits on a path that the plan creates, which is the fault of #3378.
- **Accept every literal that has a staged hit.**: The literal devops_cli.roadmap.stage_ of #3378 has a staged hit on the import lines and still fails after the move.
- **Add a new scanner beside git grep.**: The issue records git grep and the existing search_code and references tools as the covering tool, at about 10k tokens and 1 hour to build.

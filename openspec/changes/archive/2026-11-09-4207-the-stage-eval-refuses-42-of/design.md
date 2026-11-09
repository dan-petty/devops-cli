# Design

## Decisions

- **The eval gives the context builder a reader that tries the staged commit and then the checkout of the run.**: The facts describe the runner of today, and not the runner of the era of the plan. The job and the eval then run the same `collect_stage_facts_context`, and the eval has no second builder.
- **`plan_item` takes `facts_source`, and the job passes none.**: The caller chooses the reader through a parameter, so product code never detects the eval. With no `facts_source`, the reader is the staged commit only and a moved source fails the item loudly (#3258).
- **Read the checkout at `HEAD`.**: The repository of the run is the checkout of the person who runs the eval, and its `HEAD` holds the files that the runner uses now.
- **A file that neither the commit nor the checkout holds still raises `RoadmapStageError`.**: A real move of a source stays loud in the eval, and the case ends `refused` with the path.
- **Keep the dry run as it is.**: It lists the cases and builds no context. The tests prove the fault through `run_case`.

## Rejected alternatives

- **The builder leaves out a section when its file is absent.**: The job would lose its loud error when a staged source moves. A test of the job keeps that error.
- **Store the four files in each case.**: A case holds an old commit, and 54 copies of the same files go stale. The runner facts would then describe no runner.
- **A second context builder in the eval.**: The score would measure a context that the job never builds.
- **Run all 48 cases in the new test.**: One case costs about 8 seconds to read the tree, so 48 cases take 9 minutes and break the limit of 5 minutes. The measure on the base was 555 seconds. The test runs one case of each missing shape, and the hermetic tests cover the shapes.

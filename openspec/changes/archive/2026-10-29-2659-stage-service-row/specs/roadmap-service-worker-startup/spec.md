## ADDED Requirements

### Requirement: The Service imports the stage job's dependencies before its worker threads start
Before the Service starts a worker thread that runs the stage job, the main thread SHALL have imported `devops_cli.roadmap.stage`, so no two worker threads import its dependency `pydantic_ai` for the first time at the same time. The stage adapter SHALL NOT import that module inside its body.

#### Scenario: The model lane runs the stage job
- **WHEN** the module `devops_cli.roadmap.run` is read
- **THEN** it imports `devops_cli.roadmap.stage` at module level, and the body of the stage adapter holds no import of that module

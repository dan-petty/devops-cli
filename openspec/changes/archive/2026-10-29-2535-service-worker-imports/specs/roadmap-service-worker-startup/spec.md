# Spec Delta

## Purpose

The order in which the roadmap Service imports a job's dependencies against the start of its worker threads, so no two threads import a shared dependency for the first time at the same time.

## ADDED Requirements

### Requirement: The Service imports a job's dependencies before its worker threads start
Before the Service starts a worker thread that runs the refine job, the main thread SHALL have imported `devops_cli.roadmap.refine`, so no two worker threads import its dependency `pydantic_ai` for the first time at the same time.

#### Scenario: Two lanes run the refine job at the same time
- **WHEN** the Service starts and two worker lanes run the refine job in parallel
- **THEN** the main thread has imported `pydantic_ai` before either lane runs, and no lane raises an import lock error

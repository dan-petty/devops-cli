# Design

## Context

See proposal.md for the motivation and scope (#3103). The Service opens a plan pull request with the title `docs(openspec): plan #<issue> <summary>`. The command `devops roadmap plan-check` checks the plan with no model and reads the check run `Semantic PR title`.

## Goals / Non-Goals

**Goals:**
- Run the plan check on each plan pull request of the Service, and show its problems in a check run.
- Skip every other pull request with no failure.

**Non-Goals:**
- A commit status `service-vetted`, or any gate that reads the independent review.
- Make the job a required check. Only a person changes the ruleset.
- Check an implement pull request. The command reports a body problem when the body has no `Plans #`.

## Decisions

### 1. The job lives in `pr-title.yml`
- **Decision**: Put `plan-check` in the workflow that holds `semantic-title`, so `needs: semantic-title` is possible. A job can need only a job of its own workflow.
- **Alternative considered**: A new workflow that waits for the title check.
  - *Rejected*: The command needs the check run to be complete. A separate workflow has no order against `semantic-title` and would race it.

### 2. `always()` with `needs`
- **Decision**: The condition starts with `always()`. GitHub skips a job whose needed job failed, so without `always()` a failed title would hide the plan check. The command reports a failed title as a problem.
- **Alternative considered**: No `always()`.
  - *Rejected*: A plan with a bad title would show no plan problem at all.

### 3. Select by author and title
- **Decision**: The condition reads `github.event.pull_request.user.login` and the start of `github.event.pull_request.title`. It reads the author and not `github.actor`, because a person who pushes to the branch of the Service becomes the actor.
- **Alternative considered**: A ruleset condition on the head branch or on a label.
  - *Rejected*: A ruleset has conditions on `ref_name` only, and a ruleset does not run a command.

### 4. Advisory
- **Decision**: The job reports form problems only. It claims no review. The docs say so.
- **Alternative considered**: Post `service-vetted` from the job.
  - *Rejected*: The job cannot know the verdict of a review that runs outside the repository, and the plan check passed 22 of 31 plans of one window, one of which was later closed because its premise was false.

## Risks / Trade-offs

- [The plan reader gives false alarms] → The job stays advisory until a person makes it required.
- [The run takes time to set up uv and Node] → The job runs only for a Service plan, and the timeout is 10 minutes.

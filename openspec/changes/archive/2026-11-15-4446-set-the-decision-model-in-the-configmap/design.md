# Design: #4446

## Context

`render_active_devops_configmap` turns the example template into the live ConfigMap of the devops
stack. `AIConfig` sets `extra="forbid"`, so a key in the template that the image does not know
stops the pod at settings load. The template therefore held the key out until each image shipped
it (#4397).

## Decisions

- The template sets the model now, after the three live checks of 2026-11-15, so a later render
  keeps it.
- The comment gives the live check and its date, so a reader knows why the setting is safe.
- The test renders the stack as a deploy does and reads the setting, so a removed line fails.

## Risks

- A point that a later change sets to `on` without a fitted cut is refused at settings load, which
  is the guard of ADR 0020. The template names no mode, so every point keeps its default.

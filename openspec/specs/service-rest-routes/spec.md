# service-rest-routes Specification

## Purpose
The routes that the Service REST API of `devops serve` registers, and the rule that a route reports only the result of work that ran.

## Requirements

### Requirement: The Service REST API serves no canned reasoning feed
The app that `create_app()` builds SHALL register no `/v1/stream/events` route and no `/v1/ws/reasoning` route, and its OpenAPI schema SHALL list no path that starts with `/v1/stream` or `/v1/ws`. These routes sent canned events that said a security check passed when no check ran.

#### Scenario: A client asks for the reasoning feed
- **WHEN** a client sends `GET /v1/stream/events` to the app
- **THEN** the reply status is 404

#### Scenario: A client reads the API schema
- **WHEN** a client reads `/openapi.json` and the route table of the app
- **THEN** no schema path starts with `/v1/stream` or `/v1/ws`, and the route table has no `/v1/ws/reasoning` route

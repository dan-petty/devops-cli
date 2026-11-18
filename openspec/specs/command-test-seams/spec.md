# command-test-seams Specification

## Purpose
The installable seams that let a test see the ASGI app that `devops serve` starts and the due table that `devops roadmap run` prints, with no patch of a module and no real server.

## Requirements

### Requirement: The serve command starts the server through an installed starter
`devops serve` SHALL start the ASGI server through `get_server_starter`, which gives the starter that `install_server_starter` installed, and `UvicornStarter` when no starter is installed, so a test installs `FakeServerStarter` in place of a patch of `uvicorn.run`.

#### Scenario: A fake starter records the service start
- **WHEN** A test installs a `FakeServerStarter` with `install_server_starter` and runs `devops serve --service`.
- **THEN** The fake records one start call that holds the app factory and the options of the start, and the fake builds the app from that factory.

#### Scenario: The real starter serves a request on a loopback port and stops
- **WHEN** The contract test gives `UvicornStarter` a factory, a loopback port that the test process binds and a log config, and starts the server that its config describes.
- **THEN** The server answers one request on that port, the factory is called once, the server stops, and `FakeServerStarter` records the same host, port, factory flag and log config for that call.

#### Scenario: No case of the two modules patches the server start
- **WHEN** A person reads `tests/server/test_server.py` and `tests/roadmap/test_roadmap_run_service.py` after the change.
- **THEN** Each case that checks the start installs `FakeServerStarter` and reads the start call that it recorded, and neither module patches `uvicorn.run`.

### Requirement: The run command takes the due table of its round
`devops roadmap run --confirm` SHALL run the due table that `run_roadmap_command` takes, so a caller gives the round a table of its own.

#### Scenario: A failing row drives the CLI error
- **WHEN** A test calls `run_roadmap_command` with a table whose intake row raises `RoadmapRunError` with the text `[bold red]markup[/bold red]`.
- **THEN** The command exits 1 and its output holds the literal text `[bold red]markup[/bold red]`.

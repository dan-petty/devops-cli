## MODIFIED Requirements

### Requirement: Engines that stay off
The command MUST fail a row whose reply names an engine that must stay off in `results` or in `unresponsive_engines`. The engines are `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek`, `qwant`, `stackoverflow`, `askubuntu` and `superuser`, matched as a prefix. The output MUST name the engine.

#### Scenario: A keyed engine is on
- **WHEN** a reply holds a hit whose engine is `google`
- **THEN** the command exits 1 and the output names `google`.

#### Scenario: A suspended engine is listed as unresponsive
- **WHEN** `unresponsive_engines` of a reply holds the engine `bing`
- **THEN** the command exits 1 and the output names `bing`.

#### Scenario: A Stack Exchange engine is listed as unresponsive
- **WHEN** `unresponsive_engines` of a reply holds the engine `stackoverflow`
- **THEN** the command exits 1 and the output names `stackoverflow`.

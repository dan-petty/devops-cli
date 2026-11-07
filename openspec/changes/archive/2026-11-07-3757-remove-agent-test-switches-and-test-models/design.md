# Design

## Decisions

- **Remove the `"test"` name.** A string that builds a test model makes product code hold a test double. A test that needs a pydantic-ai model passes a `TestModel()` instance. `resolve_pydantic_ai_model` already returns an instance as given.
- **Prove the model edge through `pytester`.** The floor fails a test at teardown, so one test cannot assert the failure of its own call. The new test runs two inner tests through `_run_with_floor`, as the other floor tests do. The inner test without a fake catches the client error, because the floor error comes at teardown.
- **Use the real registry for the embedding cost.** `get_pricing_registry(data_dir=tmp_path)` sets the process registry, and the floor resets it after each test. The test patches nothing and spies on nothing. The provider and time check moves to `PricingRegistry.calculate_request_cost`, where the logic lives.

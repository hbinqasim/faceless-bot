# Vice Studio Engine

This package contains the common runtime pieces for future Vice Studio agents:

- `AgentResult` for consistent agent results.
- `BaseAgent` for timing, logging, and exception handling.
- `Pipeline` for running agents in order and stopping on failure.
- Resource helpers for loading JSON, loading text, saving text, creating folders, and building timestamped output paths.

## Creating an Agent

Future agents should inherit from `BaseAgent` and implement `run()`.

```python
from vice_studio.engine import AgentResult, BaseAgent


class ScriptAgent(BaseAgent):
    def run(self):
        config = self.load_config()
        prompt = self.load_prompt()

        # Do agent work here.
        output_path = "outputs/script.txt"

        return AgentResult(
            agent_name=self.agent_name,
            success=True,
            message="Script generated.",
            output_path=output_path,
            metadata={"config_keys": list(config), "prompt_length": len(prompt)},
        )
```

`execute()` should be called by tools or pipelines instead of calling `run()` directly. It starts a timer, runs the agent, returns an `AgentResult`, and converts exceptions into failed results.

```python
agent = ScriptAgent(
    agent_name="script_agent",
    config_path="vice_studio/styles/gta6.json",
    prompt_path="vice_studio/prompts/script_rules.md",
)

result = agent.execute()
```

## Pipelines

Use `Pipeline` when multiple agents need to run in sequence.

```python
from vice_studio.engine import Pipeline

pipeline = Pipeline()
pipeline.add_agent(agent)
results = pipeline.run()
```

The pipeline stops as soon as any agent returns `success=False`.

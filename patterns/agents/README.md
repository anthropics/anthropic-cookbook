# Claude Agent Framework

A lightweight framework for building tool-using agents with Claude and demonstrating workflow patterns.

## Tool-Using Agents

- `agent.py`: Core agent implementation with Claude's tool use API
- `tools/`: Reusable tool modules that agents can leverage

### Architecture

- `Tool`: Base class for all tools with a standard interface
- `Agent`: Manages conversation flow and tool dispatch

### Example Usage

```python
from agent import Agent, Tool

# Create a calculator tool
class CalculatorTool(Tool):
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"]
            },
            function=self.calculate
        )
    
    def calculate(self, expression: str) -> str:
        return str(eval(expression))

# Use the agent
agent = Agent()
agent.add_tool(CalculatorTool())
response = agent.run("What is 125 * 3.14?")
```

## Agent Workflow Patterns

This repository contains example implementations of common agent workflows:

- Basic Building Blocks
  - Prompt Chaining
  - Routing
  - Multi-LLM Parallelization
- Advanced Workflows
  - Orchestrator-Subagents
  - Evaluator-Optimizer

### Workflow Notebooks

- [Basic Workflows](basic_workflows.ipynb)
- [Evaluator-Optimizer Workflow](evaluator_optimizer.ipynb) 
- [Orchestrator-Workers Workflow](orchestrator_workers.ipynb)

## Requirements

- Python 3.9+
- Anthropic Python SDK
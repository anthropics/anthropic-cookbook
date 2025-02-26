# Claude Agent Framework

Example implementations from our blog [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents), which shares practical patterns for building effective LLM-powered systems.

## Agentic Systems

The repository demonstrates two distinct approaches to building agentic systems:

- **Workflows**: Systems where LLMs and tools are orchestrated through predefined code paths
- **Agents**: Systems where LLMs dynamically direct their own processes and tool usage

## Implementation

### Core Agent Implementation

- [`agent.py`](agent.py): Core agent implementation that uses Claude's tool use API
- `Tool`: Base class for all tools with a standard interface
- `Agent`: Manages conversation flow and tool dispatch

### Workflow Patterns

The repo includes implementations of five common workflow patterns:

1. **Prompt Chaining**: Sequential processing where outputs feed into next step
2. **Routing**: Dynamically selecting specialized paths based on input
3. **Parallelization**: Concurrent processing of independent subtasks
4. **Orchestrator-Workers**: Central LLM breaks complex tasks into dynamic subtasks
5. **Evaluator-Optimizer**: One LLM generates solutions while another evaluates

## Notebooks

- [Basic Workflows](basic_workflows.ipynb): Implementations of Prompt Chaining, Routing, and Parallelization
- [Evaluator-Optimizer Workflow](evaluator_optimizer.ipynb): Implementation of the Evaluator-Optimizer pattern
- [Orchestrator-Workers Workflow](orchestrator_workers.ipynb): Implementation of the Orchestrator-Workers pattern


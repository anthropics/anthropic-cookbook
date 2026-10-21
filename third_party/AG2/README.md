# AG2 <> Claude Cookbooks

[AG2](https://ag2.ai) (formerly AutoGen) is an open-source multi-agent framework with 500K+ monthly PyPI downloads and 4,300+ GitHub stars. It enables building multi-agent systems where agents collaborate, use tools, and solve complex tasks together.

AG2 supports Claude models natively via its Anthropic integration.

Here we provide cookbooks for building multi-agent applications using Claude and AG2:

1. `Basic_Multi_Agent_Chat.ipynb` — Set up a basic two-agent conversation with Claude, demonstrating AssistantAgent and UserProxyAgent working together.
2. `Tool_Use_With_Agents.ipynb` — Give Claude-powered agents the ability to call Python functions using AG2's tool registration decorators.
3. `GroupChat_Orchestration.ipynb` — Orchestrate multiple specialized Claude agents in a GroupChat for complex collaborative tasks.

## Getting Started

Install the AG2 framework with Anthropic support:

```bash
pip install "ag2[anthropic]>=0.11.4,<1.0"
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

## Resources

- [AG2 Documentation](https://docs.ag2.ai)
- [AG2 GitHub](https://github.com/ag2ai/ag2)
- [AG2 Discord](https://discord.gg/pAbnFJrkgZ)

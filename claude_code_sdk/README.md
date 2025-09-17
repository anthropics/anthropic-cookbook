# Building Powerful Agents with the Claude Code SDK

A tutorial series demonstrating how to build sophisticated general-purpose agentic systems using the [Claude Code SDK](https://github.com/anthropics/claude-code-sdk-python), progressing from simple research agents to multi-agent orchestration with external system integration.

## Getting Started

#### 1. Install uv, [node](https://nodejs.org/en/download/), and the Claude Code CLI (if you haven't already)

```curl -LsSf https://astral.sh/uv/install.sh | sh ```

```npm install -g @anthropic-ai/claude-code```

#### 2. Clone and set up the project

```git clone https://github.com/anthropics/anthropic-cookbook.git ```

```cd anthropic-cookbook/claude_code_sdk```

```uv sync ```

#### 3. Register venv as Jupyter kernel so that you can use it in the notebooks

```uv run python -m ipykernel install --user --name="cc-sdk-tutorial" --display-name "Python (cc-sdk-tutorial)" ```

#### 4. Claude API Key
1. Visit [console.anthropic.com](https://console.anthropic.com/dashboard)
2. Sign up or log in to your account
3. Click on "Get API keys"
4. Copy the key and paste it into your `.env` file as ```ANTHROPIC_API_KEY=```

#### 5. GitHub Token for Notebook 02
If you plan to work through the Observability Agent notebook:
1. Get a GitHub Personal Access Token [here](https://github.com/settings/personal-access-tokens/new)
2. Select "Fine-grained" token with default options (public repos, no account permissions)
3. Add it to your `.env` file as `GITHUB_TOKEN="<token>"`
4. Ensure [Docker](https://www.docker.com/products/docker-desktop/) is running on your machine

## Tutorial Series Overview

This tutorial series takes you on a journey from basic agent implementation to sophisticated multi-agent systems capable of handling real-world complexity. Each notebook builds upon the previous one, introducing new concepts and capabilities while maintaining practical, production-ready implementations.

### What You'll Learn

Through this series, you'll be exposed to:
- **Core SDK fundamentals** with `query()` and the `ClaudeSDKClient` & `ClaudeCodeOptions` interfaces in the Python SDK
- **Tool usage patterns** from basic WebSearch to complex MCP server integration
- **Multi-agent orchestration** with specialized subagents and coordination
- **Enterprise features** by leveraging hooks for compliance tracking and audit trails
- **External system integration** via Model Context Protocol (MCP)

Note: This tutorial assumes you have some level of familiarity with Claude Code. Ideally, if you have been using Claude Code to supercharge your coding tasks and would like to leverage its raw agentic power for tasks beyond Software Engineering, this tutorial will help you get started.

## Notebook Structure & Content

### [Notebook 00: The One-Liner Research Agent](00_The_one_liner_research_agent.ipynb)

Start your journey with a simple yet powerful research agent built in just a few lines of code. This notebook introduces core SDK concepts and demonstrates how the Claude Code SDK enables autonomous information gathering and synthesis.

**Key Concepts:**
- Basic agent loops with `query()` and async iteration
- WebSearch tool for autonomous research
- Multimodal capabilities with the Read tool
- Conversation context management with `ClaudeSDKClient`
- System prompts for agent specialization

### [Notebook 01: The Chief of Staff Agent](01_The_chief_of_staff_agent.ipynb)

Build a comprehensive AI Chief of Staff for a startup CEO, showcasing advanced SDK features for production environments. This notebook demonstrates how to create sophisticated agent architectures with governance, compliance, and specialized expertise.

**Key Features Explored:**
- **Memory & Context:** Persistent instructions with CLAUDE.md files
- **Output Styles:** Tailored communication for different audiences
- **Plan Mode:** Strategic planning without execution for complex tasks
- **Custom Slash Commands:** User-friendly shortcuts for common operations
- **Hooks:** Automated compliance tracking and audit trails
- **Subagent Orchestration:** Coordinating specialized agents for domain expertise
- **Bash Tool Integration:** Python script execution for procedural knowledge and complex computations

### [Notebook 02: The Observability Agent](02_The_observability_agent.ipynb)

Expand beyond local capabilities by connecting agents to external systems through the Model Context Protocol. Transform your agent from a passive observer into an active participant in DevOps workflows.

**Advanced Capabilities:**
- **Git MCP Server:** 13+ tools for repository analysis and version control
- **GitHub MCP Server:** 100+ tools for complete GitHub platform integration
- **Real-time Monitoring:** CI/CD pipeline analysis and failure detection
- **Intelligent Incident Response:** Automated root cause analysis
- **Production Workflow Automation:** From monitoring to actionable insights

## Complete Agent Implementations

Each notebook includes an agent implementation in its respective directory:
- **`research_agent/`** - Autonomous research agent with web search and multimodal analysis
- **`chief_of_staff_agent/`** - Multi-agent executive assistant with financial modeling and compliance
- **`observability_agent/`** - DevOps monitoring agent with GitHub integration

## Background
### The Evolution of Claude Code SDK

Claude Code has emerged as one of Anthropic's most successful products, but not just for its SOTA coding capabilities. Its true breakthrough lies in something more fundamental: **Claude is exceptionally good at agentic work**.

What makes Claude Code special isn't just code understanding; it's the ability to:
- Break down complex tasks into manageable steps autonomously
- Use tools effectively and make intelligent decisions about which tools to use and when
- Maintain context and memory across long-running tasks
- Recover gracefully from errors and adapt approaches when needed
- Know when to ask for clarification versus when to proceed with reasonable assumptions

These capabilities have made Claude Code the closest thing to a "bare metal" harness for Claude's raw agentic power: a minimal yet complete and sophisticated interface that lets the model's capabilities shine with the least possible overhead.

### Beyond Coding: The Agent Builder's Toolkit

Originally an internal tool built by Anthropic engineers to accelerate development workflows, the SDK's public release revealed unexpected potential. After the release of the Claude Code SDK and its GitHub integration, developers began using it for tasks far beyond coding:

- **Research agents** that gather and synthesize information across multiple sources
- **Data analysis agents** that explore datasets and generate insights
- **Workflow automation agents** that handle repetitive business processes
- **Monitoring and observability agents** that watch systems and respond to issues
- **Content generation agents** that create and refine various types of content

The pattern was clear: the SDK had inadvertently become an effective agent-building framework. Its architecture, designed to handle software development complexity, proved remarkably well-suited for general-purpose agent creation.

This tutorial series demonstrates how to leverage the Claude Code SDK to build highly efficient agents for any domain or use case, from simple automation to complex enterprise systems. 

## Contributing

Found an issue or have a suggestion? Please open an issue or submit a pull request!

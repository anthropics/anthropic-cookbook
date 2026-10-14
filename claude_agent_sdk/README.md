# Building Powerful Agents with the Claude Agent SDK

Recipes for building agents with the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python), from core SDK fundamentals to multi-agent orchestration and production deployment.

## Getting Started

#### 1. Install uv, [node](https://nodejs.org/en/download/), and the Claude Code CLI (if you haven't already)

```curl -LsSf https://astral.sh/uv/install.sh | sh```

```npm install -g @anthropic-ai/claude-code```

The `npm` step is optional unless a notebook lists the separate CLI install in its own prerequisites: the `claude-agent-sdk` package bundles the CLI.

#### 2. Clone and set up the project

```git clone https://github.com/anthropics/claude-cookbooks.git```

```cd claude-cookbooks/claude_agent_sdk```

```uv sync```

The uv environment gives you one kernel every notebook runs on. Notebooks whose first cell installs their own requirements also run on any other kernel.

#### 3. Register venv as Jupyter kernel so that you can use it in the notebooks

```uv run python -m ipykernel install --user --name="cc-sdk-tutorial" --display-name "Python (cc-sdk-tutorial)"```

#### 4. Claude API Key
1. Visit [platform.claude.com](https://platform.claude.com/dashboard)
2. Sign up or log in to your account
3. Click on "Get API keys"
4. Copy the key and paste it into your `.env` file as ```ANTHROPIC_API_KEY=```

#### 5. GitHub Token for recipe 02
If you plan to work through recipe 02, the Observability Agent:
1. Get a GitHub Personal Access Token [here](https://github.com/settings/personal-access-tokens/new)
2. Select "Fine-grained" token with default options (public repos, no account permissions)
3. Add it to your `.env` file as `GITHUB_TOKEN="<token>"`
4. Ensure [Docker](https://www.docker.com/products/docker-desktop/) is running on your machine

#### 6. Optional: import the companion agent modules
To use the foundations recipes' companion code outside the notebooks, run Python from the `claude_agent_sdk/` directory so the companion packages resolve as imports.

## What You'll Learn

Through the foundations sequence, you'll be exposed to:
- **Core SDK fundamentals** with `query()` and the `ClaudeSDKClient` & `ClaudeAgentOptions` interfaces in the Python SDK
- **Tool usage patterns** from basic WebSearch to complex MCP server integration
- **Multi-agent orchestration** with specialized subagents and coordination
- **Enterprise features** by leveraging hooks for compliance tracking and audit trails
- **External system integration** via Model Context Protocol (MCP)

Note: These recipes assume you have some level of familiarity with Claude Code. Ideally, if you have been using Claude Code to supercharge your coding tasks and would like to leverage its raw agentic power for tasks beyond Software Engineering, these recipes will help you get started.

## Foundations Sequence

The foundations sequence takes you on a journey from basic agent implementation to sophisticated multi-agent systems capable of handling real-world complexity. Each recipe builds upon the previous one, introducing new concepts and capabilities while maintaining practical, production-ready implementations.

### [00: The One-Liner Research Agent](00_The_one_liner_research_agent.ipynb)

Start your journey with a simple yet powerful research agent built in just a few lines of code. This notebook introduces core SDK concepts and demonstrates how the Claude Agent SDK enables autonomous information gathering and synthesis.

**Key Concepts:**
- Basic agent loops with `query()` and async iteration
- WebSearch tool for autonomous research
- Multimodal capabilities with the Read tool
- Conversation context management with `ClaudeSDKClient`
- System prompts for agent specialization

**Companion code:** [`research_agent/`](research_agent/)

### [01: The Chief of Staff Agent](01_The_chief_of_staff_agent.ipynb)

Build a comprehensive AI Chief of Staff for a startup CEO, showcasing advanced SDK features for production environments. This notebook demonstrates how to create sophisticated agent architectures with governance, compliance, and specialized expertise.

**Key Features Explored:**
- **Memory & Context:** Persistent instructions with CLAUDE.md files
- **Output Styles:** Tailored communication for different audiences
- **Plan Mode:** Strategic planning without execution for complex tasks
- **Custom Slash Commands:** User-friendly shortcuts for common operations
- **Hooks:** Automated compliance tracking and audit trails
- **Subagent Orchestration:** Coordinating specialized agents for domain expertise
- **Bash Tool Integration:** Python script execution for procedural knowledge and complex computations

**Companion code:** [`chief_of_staff_agent/`](chief_of_staff_agent/)

### [02: The Observability Agent](02_The_observability_agent.ipynb)

Expand beyond local capabilities by connecting agents to external systems through the Model Context Protocol. Transform your agent from a passive observer into an active participant in DevOps workflows.

**Advanced Capabilities:**
- **Git MCP Server:** 13+ tools for repository analysis and version control
- **GitHub MCP Server:** 100+ tools for complete GitHub platform integration
- **Real-time Monitoring:** CI/CD pipeline analysis and failure detection
- **Intelligent Incident Response:** Automated root cause analysis
- **Production Workflow Automation:** From monitoring to actionable insights

**Companion code:** [`observability_agent/`](observability_agent/)

### [03: The Site Reliability Agent](03_The_site_reliability_agent.ipynb)

Move from read-only observation to read-write remediation. Build an SRE incident response agent that can investigate production incidents, diagnose root causes, apply fixes, and document the results — all autonomously.

**Key Capabilities:**
- **MCP Tool Server:** 12+ tools for metrics, infrastructure, diagnostics, and documentation via JSON-RPC subprocess
- **Prometheus Integration:** PromQL queries for error rates, latency, and DB connection monitoring
- **Read-Write Remediation:** Edit configuration files, restart Docker services, and verify fixes
- **Safety Hooks:** PreToolUse hooks that validate write operations (pool size ranges, config sanity checks)
- **End-to-End Incident Lifecycle:** From detection through remediation to post-mortem documentation
- **Production Extensions:** Optional PagerDuty and Confluence integrations via conditional MCP tool registration

**Companion code:** [`site_reliability_agent/`](site_reliability_agent/)

### [04: Migrating from the OpenAI Agents SDK](04_migrating_from_openai_agents_sdk.ipynb)

Port an existing OpenAI Agents SDK application to the Claude Agent SDK, mapping each primitive across a single expense-approval agent example while both SDKs run live.

**Key Concepts:**
- **Primitive Mapping:** `@function_tool`, guardrails, and `Runner.run` to their Claude equivalents
- **Single-Agent Port:** Custom tools, input/output guardrails, multi-turn sessions, and durable resume
- **Client vs. `query()`:** When to use the stateful `ClaudeSDKClient` versus stateless `query()`
- **Observability:** Wiring the SDK's OpenTelemetry export into an existing stack

### [05: Building a Session Browser](05_Building_a_session_browser.ipynb)

Build the conversation-history sidebar users expect from an agent product, reading the SDK's on-disk session transcripts instead of writing a parser.

**Key Concepts:**
- **Listing Sessions:** Paginated session lists with branch, title, and last-modified metadata
- **Reading Transcripts:** Replay a stored session's messages without spawning the agent
- **Organizing History:** Rename, tag, and filter sessions
- **Forking:** Branch a session at any point and resume the fork as a live `query()` call

**Companion code:** [`session_browser_demo/`](session_browser_demo/)

### [06: The Vulnerability Detection Agent](06_The_vulnerability_detection_agent.ipynb)

Build a vulnerability-discovery agent that threat-models a C target, hunts memory-safety bugs with built-in file tools, and triages findings into a report a reviewer can act on.

**Key Concepts:**
- **Threat Modeling:** A bootstrap-then-interview `ClaudeSDKClient` session that writes `THREAT_MODEL.md`
- **Agentic Find Loop:** Built-in `Read`/`Grep`/`Glob` tools instead of hand-rolled file access
- **Chained Stages:** Separate find, triage, and report `query()` calls emitting schema-conformant JSON

**Companion code:** [`vulnerability_detection_agent/`](vulnerability_detection_agent/)

### [07: Hosting Your Agent](07_Hosting_the_agent.ipynb)

Deploy the research agent from recipe 00 through three tiers of operational maturity with the same container image and HTTP interface at every tier.

**Key Concepts:**
- **Docker:** Local and single-VM hosting for the dev loop and internal tools
- **Modal:** Managed serverless with a URL and scale-to-zero
- **Kubernetes:** Multi-tenant deployment in your own cluster
- **Portable Interface:** Identical agent code, image, and HTTP surface across all three tiers

**Companion code:** [`hosting/`](hosting/)

### [08: Orchestrate Subagents at Scale with Dynamic Workflows](08_Dynamic_workflows.ipynb)

Scale beyond what one context window can coordinate. Trigger dynamic workflows from the Agent SDK: Claude writes a JavaScript orchestration script for your task, and a runtime executes it across a fleet of parallel subagents in the background.

**Key Concepts:**
- **Subagents vs. Workflows:** Who holds the plan: the model's context or a deterministic script
- **Triggering Workflows from the SDK:** The `Workflow` tool, `allowed_tools`, and streaming run progress
- **Fan-Out + Adversarial Verification:** One verifier per claim in parallel, each challenged by a skeptic agent before its verdict counts
- **Reading Generated Scripts:** `agent()`, `parallel()`, `pipeline()`, phases, and structured output schemas

## Standalone Recipes

Standalone, task-shaped recipes. Each recipe lives in its own directory carrying the notebook and any supporting files.

### [Build a Scheduled Repository Reviewer](scheduled_repository_reviewer/scheduled_repository_reviewer.ipynb)

Turn recurring review toil into an unattended job you control. Build a read-only review agent that reviews a repository on a schedule, resumes its session between runs so one full baseline review is followed by short follow-ups, and proves that continuity in schema-validated fields that echo the previous review's id and findings. The notebook runs the first two cycles by hand and ends by putting the reviewer on a schedule with [`scheduled_review.py`](scheduled_repository_reviewer/scheduled_review.py), the companion script.

**Key Concepts:**
- **Read-Only Agents:** `tools` decides which built-in tools exist, `allowed_tools` decides which run without prompting, and restricting both to `Read`, `Glob`, and `Grep` leaves the agent no write tool
- **Unattended Permission Mode:** `permission_mode="dontAsk"` with pre-approved tools, plus `max_turns` and `max_budget_usd` capping the turns and spend a run can consume
- **Resumable Sessions for Continuity:** capture `session_id` from `ResultMessage`, persist it between invocations, and pass `resume` on the next run
- **Schema-Validated Continuity:** the follow-up's `output_format` schema requires the reply to echo the previous review's id and finding ids, so the resume link is a field you can assert on
- **Typed Failure Path and Greppable Output:** the `VERDICT:` line prints from the structured reply's own field, the completion line prints only after verified success, and a narrow `ResultError` catch makes a bound-exceeded run exit non-zero with `REVIEW-RUN-INCOMPLETE`

## Background
### The Evolution of Claude Agent SDK

Claude Code has emerged as one of Anthropic's most successful products, but not just for its SOTA coding capabilities. Its true breakthrough lies in something more fundamental: **Claude is exceptionally good at agentic work**.

What makes Claude Code special isn't just code understanding; it's the ability to:
- Break down complex tasks into manageable steps autonomously
- Use tools effectively and make intelligent decisions about which tools to use and when
- Maintain context and memory across long-running tasks
- Recover gracefully from errors and adapt approaches when needed
- Know when to ask for clarification versus when to proceed with reasonable assumptions

These capabilities have made Claude Code the closest thing to a "bare metal" harness for Claude's raw agentic power: a minimal yet complete and sophisticated interface that lets the model's capabilities shine with the least possible overhead.

### Beyond Coding: The Agent Builder's Toolkit

Originally an internal tool built by Anthropic engineers to accelerate development workflows, the SDK's public release revealed unexpected potential. After the release of the Claude Agent SDK and its GitHub integration, developers began using it for tasks far beyond coding:

- **Research agents** that gather and synthesize information across multiple sources
- **Data analysis agents** that explore datasets and generate insights
- **Workflow automation agents** that handle repetitive business processes
- **Monitoring and observability agents** that watch systems and respond to issues
- **Content generation agents** that create and refine various types of content

The pattern was clear: the SDK had inadvertently become an effective agent-building framework. Its architecture, designed to handle software development complexity, proved remarkably well-suited for general-purpose agent creation.

This recipe series demonstrates how to leverage the Claude Agent SDK to build highly efficient agents for any domain or use case, from simple automation to complex enterprise systems. 

## Contributing

Found an issue or have a suggestion? Please open an issue or submit a pull request!

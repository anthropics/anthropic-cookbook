# 1. Introduction

Purpose: Frame the notebook around the problem being solved and the value delivered, not the machinery being built.

### Structure

Hook with the problem (1-2 sentences)
Why it matters (1-2 sentences)
What you'll be able to do (2-4 bullet points as learning objectives)
Optional: What this unlocks (1 sentence on broader applications)
You can lead with a problem, or a value, but not with the machinery. List Terminal Learning Objectives (TLOs) and Enabling Learning Objectives (ELOs) upfront, then map them back in the conclusion. This creates a learning contract with the user.

Good: 
Your engineering team's GitHub Actions workflows fail for dozens of reasons: flaky tests, dependency conflicts, infrastructure issues, or real bugs. 

Manually triaging which failures need immediate attention versus which can wait wastes hours of senior engineer time every week. 

An AI observability agent can monitor your CI/CD pipelines 24/7, distinguish signal from noise, and escalate only what matters—cutting manual triage time by 60-80% while ensuring critical failures never slip through. 

Bad:
In this notebook we will build a research agent. Research agents are useful because they can search the internet and analyze information. We will use the Claude Code SDK to create an agent with the WebSearch tool.

You will learn how to:
- Use the `query()` function
- Set up a `ClaudeSDKClient`
- Enable the WebSearch tool
- Handle multi-turn conversations

### Template

```
## Introduction

[2-3 sentences: What's the problem? Why is it hard/important?]

[1-2 sentences: Why solving this problem matters / what value it unlocks]

**By the end of this cookbook, you'll be able to:**
- [Action verb] [specific capability] [context/constraint]
- [Action verb] [specific capability] [context/constraint]
- [Action verb] [specific capability] [context/constraint]
- [Optional 4th point for advanced outcome]

[1-2 sentences: How this pattern extends to other use cases]
```

# 2. Prerequisites & Setup
Setup the general requirements for this project that a user would need in order to be successful. These are both software requirements (e.g. python >= 3.11, anthropic>=0.71) and non-software (working knowledge of Python, familiarity with RAG architecture). 

When installing use pip, use %%capture to avoid printing pip install to the jupyter stdout (this can be very noisy).

```markdown
## Prerequisites

Before following this guide, ensure you have the following:

* [Must-have knowledge/tools - without these, the cookbook won't work]


## Setup

[Step-by-step instructions with explanations]
[Prefer `dotenv` over `os.setenv`]
```

Good:
```markdown
%%capture
%pip install -U anthropic scikit-learn voyageai

--- 

import anthropic
import dotenv

# Teaches good habits
dotenv.load_dotenv()

# constant model name is easier to change 
MODEL = "claude-haiku-4-5"

client = anthropic.Anthropic()
```

Bad:

```markdown
%pip install anthropic
%pip install foo
%pip install bar
%pip install baz
%pip install this
%pip install that

--

# Teaches bad habits
os.environ["ANTHROPIC_API_KEY"] = "YOUR_ANTHROPIC_API_KEY"

# redundant
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY')
```

### Template

```markdown
## Prerequisites

Before following this guide, ensure you have:

**Required Knowledge:**
- Python fundamentals - comfortable with functions, loops, and basic data structures
- Basic understanding of APIs and JSON

**Required Tools:**
- Python 3.11 or higher
- Anthropic API key ([get one here](https://console.anthropic.com))

**Recommended:**
- Familiarity with async/await patterns in Python
- Basic knowledge of RAG architecture concepts

## Setup

First, install the required dependencies:

~~~python
%%capture
%pip install -U anthropic scikit-learn numpy python-dotenv
~~~


**Note:** Ensure your `.env` file contains:
ANTHROPIC_API_KEY=your_key_here


Load your environment variables and configure the client:

~~~python
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

client = anthropic.Anthropic()
~~~
```


# 3. Core Cookbook Sections
Each feature/concept gets its own section that teaches through demonstration, not documentation.

You may wish to include an architecture overview, show an entire project, or build toward a larger one. Feel free to include visuals to help break up long content. Prefer inline images over linking to external content. 

Avoid feature dumps, over-explaining the obvious, and code without context. 

Code blocks should explain what they're about to do before they are introduced, and what we just learned after they are run.

4. Conclusion
Conclusions should map back to the learning objects and direct readers to other readings, links, or ideas to pursue. 

Good:
```
## Recap of what we did in this guide

In this guide, we explored how to build MCP tools that can be called programmatically via the SDK, enabling scalable and fault-tolerant workflows. We covered:

* Setting up the MCP Server
* An unoptimized example
* A better example
* Considerations for production use cases 

You can further apply these lessons in real projects. Consider the following:

1. Add additional observability through X and Y
2. Consider the performance characteristics of this problem at scale

And so on..
```
Bad:


This has less emphasis on how to apply what the reader has learned to their specific context.
```
We've demonstrated how the Claude Code SDK enables you to build sophisticated multi-agent systems
```


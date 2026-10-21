# Stock Research Agent with Grounded Base Rates

This example shows how to build a Claude-powered stock-research agent that
**never hallucinates forward-return statistics**. Instead of guessing what
"usually happens" after a chart pattern, the agent calls a single tool that
returns the real historical conditional distribution with sample size and
survivorship flag.

## The pattern

Every agent-written financial answer has a failure mode:

> "After a breakout like NVDA's, the stock typically rallies 5-10% over the next week."

That number is either invented, pulled from the model's training data (likely
stale), or loosely inspired by similar-sounding cases the model has seen. It
is **not** conditioned on the specific setup, regime, sector, or liquidity of
the query. A paying user acting on that sentence is acting on a plausible-
sounding guess.

The fix is structural: ground the claim in a retrieval call backed by real
historical data. We use [Chart Library](https://chartlibrary.io)'s cohort
primitive — one tool call, one distribution, filtered by context, with a
survivorship flag.

## What this notebook shows

1. **The problem** — side-by-side comparison of an ungrounded vs. grounded
   Claude response to the same prompt.
2. **The tool** — `get_cohort_distribution`. Given anchor (symbol, date) and
   filters, returns return/MAE/MFE/realized-vol percentiles, sample size,
   and survivorship.
3. **The loop** — Claude chooses when to call the tool, we execute it,
   results feed back, Claude writes a grounded answer.
4. **The refinement pattern** — use `refine_cohort_with_filters` and
   `explain_cohort_filters` so the agent can narrow the cohort
   progressively ("which filter actually moves the distribution?").

## Why this matters for Claude applications in finance

The next wave of AI assistants in finance will be judged on whether their
answers are wrong in ways users can't detect. A hallucinated base rate is
indistinguishable from a real one at the language level. The only structural
defense is tools that return conditional, sample-sized, survivorship-aware
data — and system prompts that force the agent to call them.

This notebook is a working minimal pattern. The tool-schema technique
transfers 1:1 to any domain where ground truth exists but is non-trivial to
retrieve.

## Run it

```bash
pip install anthropic requests
export ANTHROPIC_API_KEY=sk-ant-...
export CHART_LIBRARY_KEY=cl_...   # free key at chartlibrary.io/developers
jupyter notebook stock_research_agent.ipynb
```

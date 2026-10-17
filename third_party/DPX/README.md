# DPX <> Claude Cookbooks

[DPX](https://docs.untitledfinancial.com) is the financial action layer for AI agents — settlement infrastructure where any autonomous agent can discover, price, screen, and execute a cross-border payment end-to-end without human intervention. No API key. No onboarding. No human in the loop.

DPX publishes a native MCP server (83 tools) so Claude can call settlement, compliance, and oracle endpoints directly as tool calls — no HTTP wiring required.

## What's Included

* **[Autonomous Payment Agent Notebook](./autonomous_payment_agent.ipynb)** — A step-by-step tutorial showing how to build a Claude agent that autonomously executes a vendor payment: oracle gate → fee quote → AML/sanctions screen → on-chain settlement. Runs in sandbox mode — no real funds required.
* **[Agent-to-Agent Invoice Notebook](./agent_to_agent_invoice.ipynb)** — Two independent Claude agents settle a real payment obligation between themselves: Agent A creates an invoice, Agent B verifies and pays it by ID — no shared credentials, no out-of-band coordination beyond the invoice ID itself. Runs in sandbox mode by default; includes the real on-chain receipt (tx hashes) from an actual mainnet run.

## How to Use This Cookbook

### Step 1: Set Up Your Environment

```bash
cd third_party/DPX
python -m venv venv
source venv/bin/activate   # macOS/Linux
# or: venv\Scripts\activate  (Windows)
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
# Edit .env — only ANTHROPIC_API_KEY is required for sandbox mode
```

### Step 3: Run the Notebook

```bash
jupyter notebook autonomous_payment_agent.ipynb
```

Run all cells. The agent will:
1. Check oracle conditions
2. Get a binding fee quote
3. Screen the recipient through AML/sanctions
4. Execute the settlement (sandbox — no real USDC)
5. Print a signed receipt

## Sandbox vs Live

All examples default to `sandbox=True`. No wallet or USDC is needed for sandbox runs — the agent exercises the full settlement loop and returns realistic responses without moving real funds.

To go live: set `SANDBOX=false` in `.env` and fund a Base mainnet wallet with USDC equal to the gross settlement amount.

## DPX Free Endpoints

These endpoints require no authentication and no API key:

| Endpoint | What it does |
|---|---|
| `GET https://stability.untitledfinancial.com/reliability` | Oracle status — STABLE / CAUTION / UNSTABLE |
| `GET https://stability.untitledfinancial.com/quote` | Binding fee quote (300s TTL) |
| `GET https://agent.untitledfinancial.com/flow-check` | AML + sanctions + compliance pre-flight screen |
| `POST https://agent.untitledfinancial.com/settle` | Execute settlement (sandbox safe) |

## Additional Resources

* [DPX Docs](https://docs.untitledfinancial.com)
* [For AI Builders](https://docs.untitledfinancial.com/guides/for-ai-builders) — task-oriented examples
* [MCP Tools Reference](https://docs.untitledfinancial.com/integrations/mcp) — full 83-tool list
* [Multi-agent payments](https://docs.untitledfinancial.com/guides/multi-agent-payments) — orchestrator/sub-agent delegation

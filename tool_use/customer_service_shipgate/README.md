# Customer Service Agent Release-Readiness Check

This folder adds an optional [Agents Shipgate](https://github.com/ThreeMoonsLab/agents-shipgate) recipe for `../customer_service_agent.ipynb`, which demonstrates Claude tool use for customer lookup, order lookup, and order cancellation.

Agents Shipgate reads the local Anthropic Messages API tool artifact, policy metadata, and supplemental inventory without running the notebook, calling tools, making Anthropic API calls, or uploading source.

```bash
pipx install agents-shipgate
agents-shipgate scan -c tool_use/customer_service_shipgate/shipgate.yaml --ci-mode advisory
```

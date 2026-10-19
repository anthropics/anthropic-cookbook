# Signed receipts for tool calls

A recipe for adding a **fail-closed policy gate** and **Ed25519-signed, offline-verifiable receipts** to a Claude tool-use loop, using [protect-mcp](https://www.npmjs.com/package/protect-mcp) (the gate and signer) and [@veritasacta/verify](https://www.npmjs.com/package/@veritasacta/verify) (the offline verifier).

The notebook runs an Anthropic SDK tool-use loop where every tool call is evaluated against a [Cedar](https://www.cedarpolicy.com/) policy before it runs, signed into a tamper-evident receipt, then verified offline. It ends by tampering with a receipt to show verification fails.

See [`signed_tool_call_receipts.ipynb`](./signed_tool_call_receipts.ipynb).

Requirements: Node.js 18+ (for `npx`) and an `ANTHROPIC_API_KEY`.

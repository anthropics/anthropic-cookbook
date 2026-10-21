// One-time: create the Claude agent + environment. Runs locally with Bun/Node
// (not on the Worker). Copy the printed IDs into wrangler secrets.
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

const env = await anthropic.beta.environments.create({
  name: `cma-bridge-${Date.now()}`,
  config: { type: "cloud", networking: { type: "unrestricted" } },
});

const agent = await anthropic.beta.agents.create({
  name: "Bridge Assistant",
  model: "claude-opus-4-7",
  system:
    "You are a helpful assistant. Keep replies concise and conversational — they are posted as thread replies in chat tools. Use plain text; avoid Markdown headers.",
  tools: [{ type: "agent_toolset_20260401", default_config: { enabled: true } }],
});

console.log("\nSet these as Wrangler secrets:");
console.log(`  npx wrangler secret put CLAUDE_ENVIRONMENT_ID   # ${env.id}`);
console.log(`  npx wrangler secret put CLAUDE_AGENT_ID         # ${agent.id}`);

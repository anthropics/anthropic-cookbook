export interface Env {
  DEDUPE: KVNamespace;

  ANTHROPIC_API_KEY: string;
  ANTHROPIC_WEBHOOK_SIGNING_KEY: string;
  CLAUDE_AGENT_ID: string;
  CLAUDE_ENVIRONMENT_ID: string;

  // Slack adapter
  SLACK_SIGNING_SECRET: string;
  SLACK_BOT_TOKEN: string;
}

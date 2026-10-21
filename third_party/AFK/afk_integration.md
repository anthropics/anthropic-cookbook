# Use Claude with AFK coding-agent sessions

[AFK](https://afk.mooglest.com) is a browser-based command center for persistent coding-agent sessions. AFK supports Anthropic as a built-in LLM connection, so you can bring your Anthropic API key, choose a Claude model per session, and supervise agent work from the web UI.

Use this integration when you want Claude-powered coding-agent sessions for code changes, reviews, debugging, documentation updates, or longer-running development tasks.

## Prerequisites

- An Anthropic API key from the [Anthropic Console](https://console.anthropic.com/)
- An AFK account at [afk.mooglest.com](https://afk.mooglest.com)
- An AFK daemon connected to the machine that has access to your project files

## 1. Create or sign in to AFK

Open [afk.mooglest.com](https://afk.mooglest.com) and create an account or sign in.

AFK runs from the browser UI while a daemon gives sessions access to your local or remote project directories.

## 2. Install and connect an AFK daemon

In AFK:

1. Open **Account → API Keys**.
2. Create a daemon token.
3. Follow the install command shown in the app.
4. Confirm the daemon appears as connected in the browser.

## 3. Add Anthropic as an LLM connection

In AFK:

1. Open **Account → LLM**.
2. Click **Add connection**.
3. Choose **Anthropic**.
4. Paste your Anthropic API key.
5. Leave **Base URL** blank unless you are routing through a custom proxy or gateway.
6. Save or test the connection.

AFK uses Anthropic's default API endpoint automatically for the built-in Anthropic provider.

## 4. Start a session with Claude

Click **New session** in AFK, then:

1. Select the connected daemon and project directory.
2. Choose the Anthropic connection.
3. Select or type a Claude model name, for example:

   ```text
   claude-sonnet-4-6
   claude-opus-4-6
   claude-haiku-4-5-20251001
   ```

4. Choose a permission mode.
5. Enter the coding task and start the session.

AFK will route the session's model requests through Anthropic while the browser UI shows progress, tool usage, diffs, and session history.

## Optional: use a proxy or gateway

If your team routes Anthropic traffic through an internal gateway, set **Base URL** to that gateway's Anthropic-compatible endpoint.

Keep Base URL blank for normal Anthropic API usage.

## Troubleshooting

| Issue | Check |
|-------|-------|
| Connection test fails | Verify the Anthropic API key and confirm your network can reach Anthropic. |
| Model is missing | Manually type the Claude model name in AFK. Provider model discovery can lag behind newly released models. |
| Custom gateway errors | Confirm the Base URL points to an Anthropic-compatible endpoint. |
| Session cannot access files | Confirm the selected AFK daemon is connected and has the project directory under an allowed root. |

## Resources

- [AFK](https://afk.mooglest.com)
- [AFK provider setup docs](https://docs.mooglest.com/providers)
- [Anthropic Console](https://console.anthropic.com/)
- [Claude model overview](https://docs.claude.com/en/docs/about-claude/models/overview)

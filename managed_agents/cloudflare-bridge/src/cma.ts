import Anthropic from "@anthropic-ai/sdk";
import type { Env } from "./env";
import { adapters } from "./adapters";

// One client per isolate. Workers reuse isolates across requests, so this is
// effectively a singleton.
let _client: Anthropic | undefined;
function anthropic(env: Env): Anthropic {
  return (_client ??= new Anthropic({
    apiKey: env.ANTHROPIC_API_KEY,
    webhookKey: env.ANTHROPIC_WEBHOOK_SIGNING_KEY,
  }));
}

/**
 * Create a CMA session, stamp routing metadata (adapter name + whatever the
 * adapter needs to find its way back), send the prompt. Fire-and-forget — the
 * reply path runs in handleCmaWebhook() when Anthropic POSTs session.status_idled.
 */
export async function kickoff(
  env: Env,
  adapter: keyof typeof adapters,
  prompt: string,
  metadata: Record<string, string>,
): Promise<void> {
  const client = anthropic(env);

  const session = await client.beta.sessions.create({
    agent: env.CLAUDE_AGENT_ID,
    environment_id: env.CLAUDE_ENVIRONMENT_ID,
    metadata: { adapter, ...metadata },
  });

  await client.beta.sessions.events.send(session.id, {
    events: [
      {
        type: "user.message",
        content: [{ type: "text", text: prompt || "Hello! How can I help?" }],
      },
    ],
  });

  console.log(`[cma] kickoff adapter=${adapter} session=${session.id}`);
}

/**
 * Anthropic → bridge. Verify, dedupe, retrieve-then-filter, collect reply,
 * dispatch to the adapter named in session.metadata.adapter.
 */
export async function handleCmaWebhook(
  req: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const client = anthropic(env);
  const rawBody = await req.text();

  let event: Anthropic.Beta.BetaWebhookEvent;
  try {
    event = client.beta.webhooks.unwrap(rawBody, {
      headers: Object.fromEntries(req.headers),
    });
  } catch {
    return new Response("bad signature", { status: 401 });
  }

  // Dedupe retries (same event.id). KV because Workers isolates are per-request.
  if (await env.DEDUPE.get(`cma:${event.id}`)) {
    return new Response(null, { status: 204 });
  }
  ctx.waitUntil(env.DEDUPE.put(`cma:${event.id}`, "1", { expirationTtl: 3600 }));

  if (
    event.data.type !== "session.status_idled" &&
    event.data.type !== "session.status_terminated"
  ) {
    return new Response(null, { status: 204 });
  }

  // Process after ack so Anthropic doesn't retry on slow partner posts.
  ctx.waitUntil(process(client, env, event.data.id, event.data.type));
  return new Response(null, { status: 204 });
}

async function process(
  client: Anthropic,
  env: Env,
  sessionId: string,
  type: "session.status_idled" | "session.status_terminated",
): Promise<void> {
  // Workspace webhooks fire for EVERY session in the workspace. Retrieve and
  // filter by our metadata first; ignore anything that isn't ours.
  let session;
  try {
    session = await client.beta.sessions.retrieve(sessionId);
  } catch {
    return;
  }

  const metadata = (session.metadata ?? {}) as Record<string, string>;
  const adapter = adapters[metadata.adapter as keyof typeof adapters];
  if (!adapter) return;

  let text: string;
  if (type === "session.status_terminated") {
    text = "⚠️ Agent session terminated unexpectedly.";
  } else {
    const parts: string[] = [];
    for await (const e of client.beta.sessions.events.list(sessionId)) {
      if (e.type === "agent.message") {
        for (const block of e.content ?? []) {
          if (block.type === "text") parts.push(block.text);
        }
      }
    }
    text = parts.join("").trim();
    if (!text) return;
  }

  try {
    await adapter.postReply(metadata, text, env);
    console.log(`[cma] posted reply adapter=${metadata.adapter} session=${sessionId}`);
  } catch (err) {
    console.error(`[cma] postReply failed session=${sessionId}:`, err);
  }
}

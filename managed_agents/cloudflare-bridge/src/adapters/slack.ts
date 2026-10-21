import { createHmac, timingSafeEqual } from "node:crypto";
import type { Adapter } from "./types";
import type { Env } from "../env";
import { kickoff } from "../cma";

const TOLERANCE_SEC = 5 * 60;

export const slack: Adapter = {
  path: "/slack/events",

  async inbound(req, env, ctx) {
    const rawBody = await req.text();

    try {
      verify(rawBody, req.headers, env.SLACK_SIGNING_SECRET);
    } catch {
      return new Response("bad signature", { status: 401 });
    }

    const payload = JSON.parse(rawBody);

    if (payload.type === "url_verification") {
      return new Response(payload.challenge, {
        headers: { "content-type": "text/plain" },
      });
    }
    if (payload.type !== "event_callback") {
      return new Response(null, { status: 204 });
    }

    // Dedupe Slack retries
    if (await env.DEDUPE.get(`slack:${payload.event_id}`)) {
      return new Response(null, { status: 204 });
    }
    ctx.waitUntil(
      env.DEDUPE.put(`slack:${payload.event_id}`, "1", { expirationTtl: 3600 }),
    );

    const ev = payload.event;
    const isMention = ev.type === "app_mention";
    const isDM = ev.type === "message" && ev.channel_type === "im" && !ev.subtype;
    if ((!isMention && !isDM) || ev.bot_id || !ev.text) {
      return new Response(null, { status: 204 });
    }

    // Fire-and-forget so Slack gets its 2xx within 3s.
    ctx.waitUntil(
      kickoff(env, "slack", stripMention(ev.text), {
        slack_channel: ev.channel,
        slack_thread_ts: ev.thread_ts ?? ev.ts,
        slack_team: payload.team_id,
      }).catch((err) => console.error("[slack] kickoff error:", err)),
    );

    return new Response(null, { status: 204 });
  },

  async postReply(metadata, text, env) {
    const res = await fetch("https://slack.com/api/chat.postMessage", {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.SLACK_BOT_TOKEN}`,
        "content-type": "application/json; charset=utf-8",
      },
      body: JSON.stringify({
        channel: metadata.slack_channel,
        thread_ts: metadata.slack_thread_ts,
        text,
      }),
    });
    const body = (await res.json()) as { ok: boolean; error?: string };
    if (!body.ok) throw new Error(`slack chat.postMessage: ${body.error}`);
  },
};

// Slack request signing:
// sig = "v0=" + hex(HMAC-SHA256(secret, "v0:{timestamp}:{body}"))
function verify(rawBody: string, headers: Headers, secret: string): void {
  const timestamp = headers.get("x-slack-request-timestamp");
  const signature = headers.get("x-slack-signature");
  if (!timestamp || !signature) throw new Error("missing headers");
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp, 10)) > TOLERANCE_SEC) {
    throw new Error("timestamp outside tolerance");
  }
  const expected =
    "v0=" +
    createHmac("sha256", secret).update(`v0:${timestamp}:${rawBody}`).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new Error("signature mismatch");
  }
}

function stripMention(text: string): string {
  return text.replace(/<@[A-Z0-9]+>/g, "").trim();
}

import type { Env } from "../env";

/** A partner integration: how to receive inbound events, and how to post a reply back. */
export interface Adapter {
  /** Route path for the partner's inbound webhook (e.g. "/slack/events"). */
  path: string;

  /**
   * Handle the partner's inbound webhook. Verify signature, extract the user's
   * prompt, and call `kickoff()` (fire-and-forget via ctx.waitUntil). Return a
   * Response quickly — partners typically have a 3–10s ack window.
   */
  inbound(req: Request, env: Env, ctx: ExecutionContext): Promise<Response>;

  /**
   * Post the agent's reply back to the partner. `metadata` is whatever this
   * adapter put on the CMA session at kickoff time — the CMA side treats it
   * as opaque.
   */
  postReply(metadata: Record<string, string>, text: string, env: Env): Promise<void>;
}

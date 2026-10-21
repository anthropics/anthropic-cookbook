import type { Env } from "./env";
import { adapters } from "./adapters";
import { handleCmaWebhook } from "./cma";

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    if (url.pathname === "/" && req.method === "GET") {
      return Response.json({ status: "ok", adapters: Object.keys(adapters) });
    }

    // Anthropic → us
    if (url.pathname === "/cma-webhook" && req.method === "POST") {
      return handleCmaWebhook(req, env, ctx);
    }

    // Partner → us
    if (req.method === "POST") {
      for (const adapter of Object.values(adapters)) {
        if (url.pathname === adapter.path) {
          return adapter.inbound(req, env, ctx);
        }
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};

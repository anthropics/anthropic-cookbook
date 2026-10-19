# Hosting the research agent

This directory deploys the research agent from
[`00_The_one_liner_research_agent.ipynb`](../00_The_one_liner_research_agent.ipynb)
through four tiers: local Docker, Modal, Kubernetes, and Google Cloud Run. The agent, the
container image, and the HTTP interface are the **same** across all three —
only the operational machinery around the container changes.

Walk through [`07_Hosting_the_agent.ipynb`](../07_Hosting_the_agent.ipynb) for
the full narrative.

## Interface contract

All tiers conform to this contract. The Kubernetes gateway routes against it.

```
The agent image exposes:

  GET  /health
       → 200 {"status": "ok"}
       Liveness check for orchestration.

  POST /sessions/{session_id}/messages
       Body: {"prompt": "<user message>"}
       → 200 text/event-stream
         event: message  — data is a serialized SDK message
                           (SystemMessage | AssistantMessage | ResultMessage)
         event: done     — turn complete
         event: error    — data is {"message": "..."}
       Resumes the session if it exists, creates if not.
       Stream contains ONLY the new turn's events, not history.

  session_id MUST match ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$. Invalid → 400.

  Port: 8000
  Required env: ANTHROPIC_API_KEY
  Optional env: MODEL (default: claude-sonnet-4-6),
                CLAUDE_CONFIG_DIR (default: /data — mount this for persistence),
                AGENT_AUTH_TOKEN (when set, /sessions/* requires
                                  Authorization: Bearer <token>; /health stays open)

  ⚠️  SECURITY: This server has no authentication by default. It MUST sit
      behind a gateway/proxy that (1) authenticates callers and (2) only
      forwards session_ids that belong to the authenticated caller. Do not
      expose port 8000 to the internet directly.

      If there is no gateway (tier 2: Modal hands out a public tunnel), set
      AGENT_AUTH_TOKEN. It is the minimal stand-in, not a replacement — it
      does not scope session_ids to callers.

  LIFECYCLE: The server does not self-terminate. The orchestrator is
      responsible for killing idle containers.
```

## Directory layout

```
hosting/
  README.md            ← you are here
  Dockerfile           ← shared agent image (build context = claude_agent_sdk/)
  Dockerfile.dockerignore
  server.py            ← FastAPI + SSE server (the hybrid path)
  run_once.py          ← ephemeral path: one prompt, print result, exit
  entrypoint.sh        ← dispatches: ephemeral run vs. start server
  requirements.txt
  .env.example         ← ANTHROPIC_API_KEY, MODEL
  docker/              ← Tier 1: local Docker / docker-compose
  modal/               ← Tier 2: Modal Sandbox
  kubernetes/          ← Tier 3: pod-per-session on your own k8s cluster
  cloud_run/           ← Tier 4: Google Cloud Run (serverless, scale-to-zero)
```

## Build

The Docker build context is the **parent** directory (`claude_agent_sdk/`), not
`hosting/`, because the image needs `research_agent/` and `utils/` alongside
`hosting/`:

```bash
cd claude_agent_sdk/
docker build -f hosting/Dockerfile -t research-agent .
```

> The build uses the sibling `Dockerfile.dockerignore` (note the prefixed name),
> which requires BuildKit — the default builder in Docker 23.0+ and Docker
> Desktop. On an older engine, run the build with `DOCKER_BUILDKIT=1`.

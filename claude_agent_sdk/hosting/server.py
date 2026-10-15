"""FastAPI wrapper that exposes the research agent over HTTP + SSE.

⚠️  SECURITY — READ THIS BEFORE DEPLOYING
This server has **no authentication by default**. It trusts whoever can reach
port 8000. It MUST sit behind a gateway/proxy that (1) authenticates callers
and (2) only forwards ``session_id`` values that belong to the authenticated
caller. Never expose this port to the internet directly. See the interface
contract in ``hosting/README.md``.

When there *is no* gateway in front (tier 2 hands out a public Modal tunnel),
set ``AGENT_AUTH_TOKEN`` and the server requires ``Authorization: Bearer
<token>`` on the messages endpoint. This is the minimal stand-in for the
gateway, not a replacement for one.

The server is deliberately thin: it doesn't manage lifecycle (the orchestrator
kills idle containers), doesn't manage auth (the gateway does), and doesn't
transform SDK messages (clients get the raw types). Its only jobs are to run
the agent, stream its messages, and let conversations resume.

One design note: the SDK generates its own session IDs — you can't choose them.
So this server keeps a small persisted map from the caller's ``session_id``
(the path parameter) to the SDK's internal ID, and passes the internal ID to
``resume=`` on follow-up turns. The map lives alongside the transcripts under
``CLAUDE_CONFIG_DIR`` so it survives restarts the same way the sessions do.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# The agent we built in notebook 00. We import its system prompt so this server
# deploys *that* agent; the tool list and buffer size below mirror send_query().
from research_agent.agent import RESEARCH_SYSTEM_PROMPT
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

# Same shape the k8s gateway enforces: must start alphanumeric so a session_id
# can never begin with "-" or "_" (keeps it safe as a filename or k8s label).
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
# Opt-in bearer token for deployments with no gateway in front (tier 2). Unset
# by default so tiers that *do* have a gateway (tier 3) aren't double-checking.
AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN")
CONFIG_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", "/data"))
SESSION_MAP_PATH = CONFIG_DIR / "hosting_session_map.json"
# Notebook 00's agent also enables Read so you can hand it a local chart from
# your laptop. The hosted server intentionally drops it: there's no upload path,
# so the only thing Read can reach inside the container is the container itself
# (other sessions' transcripts in /data, /proc/self/environ with the API key).
# A prompt-injected web result could walk the agent into exfiltrating those.
# Hosted research = WebSearch only.
ALLOWED_TOOLS = ["WebSearch"]
MAX_BUFFER_SIZE = 10 * 1024 * 1024
# Reject oversized request bodies before they hit the JSON parser. 256 KB is
# generous for a prompt; a production deployment would also enforce this at
# the gateway.
MAX_BODY_BYTES = 256 * 1024
# Default to Sonnet so running the notebook end-to-end stays cheap. Override
# with MODEL=claude-opus-5-5 to match notebook 00's DEFAULT_MODEL exactly.
DEFAULT_MODEL = "claude-sonnet-5-5"

_session_map: dict[str, str] = {}  # external session_id → SDK session_id
_map_lock = asyncio.Lock()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if SESSION_MAP_PATH.exists():
        _session_map.update(json.loads(SESSION_MAP_PATH.read_text()))
    yield


app = FastAPI(title="Research Agent (Claude Agent SDK)", lifespan=_lifespan)


# Only enforces the cap for requests with Content-Length; chunked bodies
# pass through. In production put a real body-size limit on the gateway/LB.
@app.middleware("http")
async def _limit_body_size(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    return await call_next(request)


class MessageIn(BaseModel):
    prompt: str


def _require_token(authorization: str | None = Header(default=None)) -> None:
    """Reject the request unless it carries the expected bearer token.

    No-op when ``AGENT_AUTH_TOKEN`` is unset — the gateway is doing the work.
    Uses ``compare_digest`` so the check isn't a timing oracle.
    """
    if AUTH_TOKEN is None:
        return
    expected = f"Bearer {AUTH_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="missing or invalid token")


@app.get("/health")
async def health() -> dict[str, str]:
    # Deliberately unauthenticated — orchestrators probe this for liveness.
    return {"status": "ok"}


@app.post("/sessions/{session_id}/messages", dependencies=[Depends(_require_token)])
async def post_message(session_id: str, body: MessageIn) -> EventSourceResponse:
    if not SESSION_ID_RE.fullmatch(session_id):
        # session_id flows into the persisted map and ultimately a filesystem
        # lookup — this validation is a security control, not cosmetics.
        raise HTTPException(status_code=400, detail="invalid session_id")

    sdk_session_id = _session_map.get(session_id)
    options = _build_options(resume=sdk_session_id)
    return EventSourceResponse(_stream_turn(session_id, body.prompt, options))


def _build_options(*, resume: str | None) -> ClaudeAgentOptions:
    """Build the same agent config as notebook 00, plus hosting concerns."""
    return ClaudeAgentOptions(
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        max_buffer_size=MAX_BUFFER_SIZE,
        model=os.environ.get("MODEL", DEFAULT_MODEL),
        # Must match the Dockerfile WORKDIR for resume to find transcripts.
        cwd="/app",
        resume=resume,
    )


async def _stream_turn(
    external_id: str, prompt: str, options: ClaudeAgentOptions
) -> AsyncIterator[ServerSentEvent]:
    try:
        async for message in query(prompt=prompt, options=options):
            yield ServerSentEvent(event="message", data=_serialize(message))
            if isinstance(message, ResultMessage) and message.session_id:
                # First turn on a new external_id: learn the SDK's generated ID
                # so follow-ups can resume it.
                await _remember(external_id, message.session_id)
        yield ServerSentEvent(event="done", data="")
    except Exception as exc:  # noqa: BLE001 — surface any agent error to the stream
        yield ServerSentEvent(event="error", data=json.dumps({"message": str(exc)}))


async def _remember(external_id: str, sdk_session_id: str) -> None:
    # Note: two concurrent *first* turns on the same external_id would each
    # start a fresh SDK session and last-write-wins here. Fine for this
    # cookbook's single-caller-per-session shape; a production server would
    # lock around the read-create-write span, not just the write. The
    # Kubernetes tier avoids this race with Redis SET NX — see
    # kubernetes/gateway/k8s.py.
    async with _map_lock:
        if _session_map.get(external_id) == sdk_session_id:
            return
        _session_map[external_id] = sdk_session_id
        tmp = SESSION_MAP_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_session_map))
        tmp.replace(SESSION_MAP_PATH)


def _serialize(message: Any) -> str:
    """Serialize an SDK message to JSON.

    SDK messages are dataclasses; ``dataclasses.asdict`` handles the nesting.
    ``default=str`` catches anything that isn't natively JSON-encodable.
    We tag with ``type`` so clients can switch on the message class without
    having to infer it from shape.
    """
    payload = asdict(message) if is_dataclass(message) else {"value": message}
    payload["type"] = type(message).__name__
    return json.dumps(payload, default=str)

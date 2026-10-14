# Self-hosted sandbox for the MongoDB cookbook

This is the image behind **Path B** of the
[MongoDB Atlas cookbook](../../CMA_with_mongodb_atlas.ipynb): a self-hosted
sandbox that bundles `pymongo`, so the agent can query MongoDB from its `bash`
tool. It lives here because that notebook depends on it. The general-purpose
self-hosted sandbox demos, with Docker and five cloud providers, are in
[claude-quickstarts](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/self-hosted-sandboxes).

The host runs `ant beta:worker poll` directly; per claimed work item its
`--on-work` script (`on-work.sh`) `docker run`s a per-session container whose
entrypoint is `ant beta:worker run`. Each container gets a `/workspace` (the
agent's working tree; skills download here) backed by a per-session Docker
volume so the tree and skills survive across containers for one session.

It is plain Docker on a host you control, with the same CLI and the same env
contract as the
[`docker/` quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/self-hosted-sandboxes/docker).

- **`Dockerfile`** — the per-session image: pinned `ant` CLI, `WORKDIR
  /workspace`, `ENTRYPOINT ["ant","beta:worker","run", …]`. The CLI owns
  heartbeat, backlog reconcile, SSE, the `bash`/`read`/`write`/`edit`/`glob`/
  `grep` toolset, and the work-item force-stop on exit.
- **`on-work.sh`** — invoked by the poller per work item. Reads the
  `ANTHROPIC_{WORK_ID,ENVIRONMENT_ID,SESSION_ID,ENVIRONMENT_KEY}` the poller
  sets, drains the work JSON on stdin, and `exec`s a `--rm` per-session
  container in the **foreground** (idempotent: a duplicate item for a live
  session is a no-op). It blocks until the container exits — it must, because
  `ant beta:worker poll` posts a stop on the work item the moment the
  `--on-work` script returns (no CLI opt-out). A detached `docker run -d` would
  let the poller stop the work before the container could claim it, so the
  `bash` tool call would never run.
- **`start.sh`** — builds the image and execs the host poller with
  `--on-work on-work.sh`.

Idle policy is the SDK default: each container exits 60s after
`session.status_idle` with `stop_reason: end_turn`; any other event resets the
clock. `--rm` then removes it; the per-session volume persists for the next
message in that session.

No org API key anywhere: the only credential is the **environment key**. The
poller uses it to claim work; it's passed into each container as
`ANTHROPIC_ENVIRONMENT_KEY` (the per-session calls — event stream, lease
heartbeat, force-stop) **and** as `ANTHROPIC_AUTH_TOKEN` (the CLI's
skill-download client resolves only `ANTHROPIC_API_KEY` /
`ANTHROPIC_AUTH_TOKEN`, not `ANTHROPIC_ENVIRONMENT_KEY` — without it skills
silently fail to download).

## Querying MongoDB from the sandbox

This image bundles `python3` + `pymongo`, and `on-work.sh` forwards an optional `MONGO_URI`
into each per-session container, so the agent can query MongoDB straight from its `bash` tool:

```sh
python3 -c 'import os; from pymongo import MongoClient; \
c = MongoClient(os.environ["MONGO_URI"]); \
print(list(c["mydb"]["mycoll"].find({}, {"_id": 0}).limit(5)))'
```

Set it host-side before `./start.sh` (it flows poller → `on-work.sh` → container):

```sh
export MONGO_URI="mongodb+srv://<user>:<password>@<cluster>/"
```

`MONGO_URI` is **your** secret, not Anthropic's. Because this is a container you build and run,
it's a normal env var that never reaches the control plane or the session event history — the
self-hosted advantage. (A *cloud* sandbox has no env-var or vault channel for a database secret,
so there you keep the credential host-side behind a custom tool instead. See the
[MongoDB-on-CMA landing page](../README.md) and the
[cookbook](../../CMA_with_mongodb_atlas.ipynb), whose Section 1
walks all three connection paths.)

The agent's `bash` runs inside this container, so it can read `MONGO_URI` — fine when you trust
the task. For least privilege, swap the built-in toolset for your own worker tool that exposes a
narrow `mongo_query(...)` instead of the raw URI. Prefer the MongoDB shell? Add `mongosh` to the
image (MongoDB's apt repo) and call `mongosh "$MONGO_URI" --eval '…'`.

## Prerequisites

- Docker
- `ant` on the host's PATH, the **same build** pinned in `Dockerfile`
  (`ARG ANT_VERSION`). Install it:

  ```sh
  VERSION=1.10.0   # must match ANT_VERSION in Dockerfile
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
  curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${VERSION}/ant_${VERSION}_${OS}_${ARCH}.tar.gz" \
    | sudo tar -xz -C /usr/local/bin ant
  ant --version
  ```

## Run

```sh
export ANTHROPIC_ENVIRONMENT_ID=env_...
export ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat...
./start.sh
```

Then create a session pointing at that `ANTHROPIC_ENVIRONMENT_ID` and send it a
message. You should see, in order:

```
[start] polling env=env_... base=https://api.anthropic.com
[on-work] session=sesn_... work=work_... container=... (started)
```

Container logs (`docker logs cma-sesn_...`) show the `ant beta:worker run`
JSON: `downloaded skill …`, `executing tool …`, etc. The container removes
itself after it idles out; the `cma-ws-<session_id>` volume remains for that
session's next message (`docker volume rm` to discard).

Unlike the [webhook-started providers](https://github.com/anthropics/claude-quickstarts/tree/main/managed-agents/self-hosted-sandboxes) in claude-quickstarts, there is no
webhook here — `ant beta:worker poll` long-polls the environment directly, so
nothing needs to be exposed to the internet.

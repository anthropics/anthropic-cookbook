# Tier 4 — Google Cloud Run

Runs the **same** `hosting/Dockerfile` image on
[Google Cloud Run](https://cloud.google.com/run): a fully managed, serverless
container platform with scale-to-zero, an HTTPS endpoint, the key held in Secret
Manager, and IAM as the front door.

Where Modal (tier 2) hands you a public tunnel guarded by a bearer token, Cloud
Run puts Google IAM in front of the container — which is exactly the
"authenticating gateway" the [interface contract](../README.md#interface-contract)
asks for. That is the default here.

## Prerequisites

```bash
gcloud config set project YOUR_PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

# Put the API key in Secret Manager (never in the image or an env var):
printf '%s' "$ANTHROPIC_API_KEY" | \
  gcloud secrets create anthropic-api-key --data-file=-
```

## Deploy

```bash
cd claude_agent_sdk/
PROJECT=YOUR_PROJECT hosting/cloud_run/deploy.sh
```

`deploy.sh` builds the shared Dockerfile with Cloud Build (build context =
`claude_agent_sdk/`, same as every other tier), pushes it to Artifact Registry,
and deploys a Cloud Run service that runs the container in **`serve`** mode on
port **8000**, reads `ANTHROPIC_API_KEY` from Secret Manager, is **IAM-protected**
(`--no-allow-unauthenticated`), and scales to zero.

## Talk to it

The service is IAM-protected, so reach it through an authenticated proxy:

```bash
gcloud run services proxy research-agent --region=us-central1 --port=8080
# then, in another shell:
curl -s localhost:8080/health
# {"status": "ok"}

curl -sN -X POST localhost:8080/sessions/demo-1/messages \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What are the latest AI agent trends?"}'
```

For CI or service-to-service calls, grant the caller `roles/run.invoker` and send
a Google-signed ID token whose audience is the service URL.

### Public demo (optional)

If you just want a public URL to curl — the same posture as the Modal tier —
deploy with a bearer token instead of IAM. `/health` stays open; `/sessions/*`
requires the token:

```bash
TOKEN=$(openssl rand -hex 16)
gcloud run deploy research-agent --region=us-central1 \
  --image="$IMAGE" --args=serve --port=8000 \
  --update-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars=CLAUDE_CONFIG_DIR=/tmp/data,AGENT_AUTH_TOKEN="$TOKEN" \
  --allow-unauthenticated

URL=$(gcloud run services describe research-agent --region=us-central1 --format='value(status.url)')
curl -sN -X POST "$URL/sessions/demo-1/messages" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"What are the latest AI agent trends?"}'
```

This is the minimal stand-in the contract describes, not a replacement for the
IAM gateway.

## Persistence

Cloud Run's container filesystem is **read-only except for an in-memory `/tmp`**,
so `deploy.sh` points `CLAUDE_CONFIG_DIR` at `/tmp/data`. Sessions work, but they
are ephemeral — a cold start or a second instance starts empty. `deploy.sh` sets
`--session-affinity` so a caller tends to land back on the same warm instance,
which is enough for resume within a session's lifetime.

For durable, shared sessions, mount a Cloud Storage bucket at `/data` and drop
the `CLAUDE_CONFIG_DIR` override so it falls back to the `/data` default:

```bash
gcloud run services update research-agent --region=us-central1 \
  --add-volume=name=sessions,type=cloud-storage,bucket=YOUR_BUCKET \
  --add-volume-mount=volume=sessions,mount-path=/data \
  --remove-env-vars=CLAUDE_CONFIG_DIR
```

> Same caveat as the Modal tier: the SDK writes many small transcript files, and
> GCS FUSE across concurrent instances is not built for that. For real
> multi-instance use, switch to a
> [`SessionStore`](https://code.claude.com/docs/en/agent-sdk/session-storage)
> backed by an external store — the same move tier 3 makes.

## Liveness

Cloud Run restarts unresponsive containers and scales to zero on its own. To have
it recycle a *wedged* server (process up, not answering), add a liveness probe on
`GET /health` — via the service YAML or the console's container health-check
settings.

## Teardown

```bash
PROJECT=YOUR_PROJECT hosting/cloud_run/teardown.sh
```

Deletes the service and the built image so you are not billed for idle resources.

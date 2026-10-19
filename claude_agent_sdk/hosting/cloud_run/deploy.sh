#!/usr/bin/env bash
# Deploy the research agent to Google Cloud Run. Run from claude_agent_sdk/:
#
#   cd claude_agent_sdk/
#   PROJECT=my-gcp-project hosting/cloud_run/deploy.sh
#
# Reuses the SAME hosting/Dockerfile image as every other tier; only the
# operational machinery (Cloud Build + Cloud Run + Secret Manager) is specific
# to Cloud Run.
set -euo pipefail

PROJECT="${PROJECT:?set PROJECT to your GCP project id}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-research-agent}"
# Artifact Registry repo. cloud-run-source-deploy is the one Cloud Run's own
# source deploys create, so it usually already exists; any repo works.
REPO="${REPO:-cloud-run-source-deploy}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

# The key lives in Secret Manager, never in the image or an env var. Create it
# once (skip if it already exists):
#   printf '%s' "$ANTHROPIC_API_KEY" | \
#     gcloud secrets create anthropic-api-key --data-file=- --project="$PROJECT"
# Let Cloud Run's runtime service account read it:
SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --project="$PROJECT" --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

# Build the shared image (context = ., i.e. claude_agent_sdk/; Dockerfile = hosting/Dockerfile).
gcloud builds submit --project="$PROJECT" \
  --config=hosting/cloud_run/cloudbuild.yaml \
  --substitutions=_IMAGE="$IMAGE" .

# Deploy. Notes:
#   --args=serve             run the FastAPI server (entrypoint's serve mode),
#                            not the one-shot run_once runner
#   --port=8000              the server listens on 8000
#   --update-secrets         inject the key from Secret Manager at runtime
#   CLAUDE_CONFIG_DIR=/tmp/data  Cloud Run's filesystem is read-only except an
#                            in-memory /tmp; see README "Persistence" for durable
#                            sessions on a mounted bucket
#   --no-allow-unauthenticated  Cloud Run IAM is the authenticating gateway the
#                            server's interface contract requires
#   --session-affinity       best-effort routing of a caller back to the same
#                            instance, so filesystem-backed session resume sticks
gcloud run deploy "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --image="$IMAGE" \
  --args=serve \
  --port=8000 \
  --update-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars=CLAUDE_CONFIG_DIR=/tmp/data \
  --no-allow-unauthenticated \
  --session-affinity \
  --min-instances=0 --max-instances=4 \
  --memory=1Gi --cpu=1 --timeout=300

cat <<EOF

Deployed "$SERVICE" to Cloud Run (IAM-protected, no public access).
Reach it locally through an authenticated proxy:

  gcloud run services proxy $SERVICE --region=$REGION --project=$PROJECT --port=8080
  curl -s localhost:8080/health

See README.md "Talk to it" for a public bearer-token demo and CI access.
EOF

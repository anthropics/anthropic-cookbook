#!/usr/bin/env bash
# Delete the Cloud Run service and the built image so you are not billed for
# idle resources.
#
#   PROJECT=my-gcp-project hosting/cloud_run/teardown.sh
set -euo pipefail

PROJECT="${PROJECT:?set PROJECT to your GCP project id}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-research-agent}"
REPO="${REPO:-cloud-run-source-deploy}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

gcloud run services delete "$SERVICE" --project="$PROJECT" --region="$REGION" --quiet || true
gcloud artifacts docker images delete "$IMAGE" --project="$PROJECT" --quiet || true

echo "Removed the $SERVICE service and image. The anthropic-api-key secret is left in place."

#!/usr/bin/env bash
# Invoked by `ant beta:worker poll --on-work` once per claimed work item.
#
# The poller passes ANTHROPIC_{WORK_ID,ENVIRONMENT_ID,SESSION_ID,ENVIRONMENT_KEY}
# in the environment and the raw work JSON on stdin (drained, unused here).
# ANTHROPIC_BASE_URL is inherited from the poller process.
#
# Per work item this starts a detached, per-session Docker container running
# `ant beta:worker run` (the image's ENTRYPOINT) against a per-session volume
# mounted at /workspace, then exits so the poller can claim the next item.
set -euo pipefail

cat >/dev/null  # drain the work JSON on stdin

: "${ANTHROPIC_SESSION_ID:?on-work: ANTHROPIC_SESSION_ID not set by poller}"
: "${ANTHROPIC_ENVIRONMENT_ID:?on-work: ANTHROPIC_ENVIRONMENT_ID not set by poller}"
: "${ANTHROPIC_WORK_ID:?on-work: ANTHROPIC_WORK_ID not set by poller}"
: "${ANTHROPIC_ENVIRONMENT_KEY:?on-work: ANTHROPIC_ENVIRONMENT_KEY not set by poller}"

IMAGE="${CMA_IMAGE:-cma-self-hosted-sandbox-docker}"
NAME="cma-${ANTHROPIC_SESSION_ID}"     # session ids are docker-name-safe
VOLUME="cma-ws-${ANTHROPIC_SESSION_ID}"

# Idempotent: a duplicate work item for a session already being served is a
# no-op (the live container's `ant beta:worker run` owns that session). The
# work-item lease lapses and the next webhook/poll reclaims it once the
# container has idled out.
if [ -n "$(docker ps -q --filter "name=^${NAME}$" 2>/dev/null)" ]; then
  echo "[on-work] session=${ANTHROPIC_SESSION_ID} already has a live container; skipping" >&2
  exit 0
fi
docker rm -f "$NAME" >/dev/null 2>&1 || true  # clear any exited leftover

# Foreground (exec, no -d): this script MUST stay alive for the session's whole
# lifetime. `ant beta:worker poll` posts a stop on the work item as soon as the
# --on-work script exits, and there is no CLI flag to opt out — so a detached
# `docker run -d` that returned immediately would make the poller stop the work
# before the just-spawned container could claim it ("heartbeat reports shutdown,
# state stopped" → the tool call never runs). Blocking here keeps the work item
# live until `ant beta:worker run` finishes (it idles out 60s after end_turn).
# --rm removes the container on exit; the per-session volume persists.
# ANTHROPIC_AUTH_TOKEN is set to the environment key because the CLI's
# skill-download client only resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN,
# not ANTHROPIC_ENVIRONMENT_KEY — without it skills silently fail to download.
# MONGO_URI (optional) is YOUR database secret, not Anthropic's — forwarded into the
# per-session container as a normal env var so the agent can query MongoDB from bash. Because
# this is a self-hosted container, the secret stays here: it never reaches the control plane or
# the session event history (a cloud sandbox has no env-var channel — there you keep the
# credential host-side behind a custom tool instead). The agent's bash CAN read it, which is
# fine when you trust the task; for least privilege, expose a narrow query via your own tool
# rather than the raw URI. Unset MONGO_URI is passed through as empty (a no-op). See README.
echo "[on-work] session=${ANTHROPIC_SESSION_ID} work=${ANTHROPIC_WORK_ID} (running container in foreground)" >&2
exec docker run --rm --name "$NAME" \
  -v "${VOLUME}:/workspace" \
  -e "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}" \
  -e "ANTHROPIC_ENVIRONMENT_KEY=${ANTHROPIC_ENVIRONMENT_KEY}" \
  -e "ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_ENVIRONMENT_KEY}" \
  -e "ANTHROPIC_SESSION_ID=${ANTHROPIC_SESSION_ID}" \
  -e "ANTHROPIC_ENVIRONMENT_ID=${ANTHROPIC_ENVIRONMENT_ID}" \
  -e "ANTHROPIC_WORK_ID=${ANTHROPIC_WORK_ID}" \
  -e "MONGO_URI=${MONGO_URI:-}" \
  "$IMAGE"

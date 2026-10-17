"""
Kubernetes pod lifecycle management for agent sessions.

Creates, monitors, and deletes per-session agent pods using the K8s API.
Maintains a standby pool of pre-warmed pods so new sessions start instantly
instead of waiting 30-60s for a cold pod to pull its image and boot.

Key concepts for K8s newcomers:
- A "Pod" is the smallest deployable unit in K8s — think of it as a wrapper
  around one or more containers (we use one container per pod here).
- "Labels" are key/value tags on K8s objects.  We use them to track which pods
  are standby vs. active, and which session owns a pod.
- The K8s API is synchronous/blocking, so every call is wrapped in
  `asyncio.to_thread()` to avoid blocking the async event loop.
"""

import asyncio
import logging
import os
import uuid

import kubernetes
from kubernetes import client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level K8s configuration
# ---------------------------------------------------------------------------
# load_incluster_config() reads the service-account token that K8s
# automatically mounts into every pod at /var/run/secrets/kubernetes.io/.
# It only works when this code runs *inside* a K8s cluster.
# When running locally (e.g. tests, dev server) it will fail — we catch
# that and flip a flag so the rest of the gateway can still import this module.
_k8s_available = True

try:
    kubernetes.config.load_incluster_config()
except kubernetes.config.ConfigException:
    logger.warning(
        "Failed to load in-cluster K8s config — running outside Kubernetes. "
        "Pod management functions will be unavailable."
    )
    _k8s_available = False

# AGENT_IMAGE is the container image for agent pods (e.g. "us-docker.pkg.dev/…/agent:latest").
# Required when K8s is available; ignored otherwise. Validated at startup
# (initialize_standby_pool), not import time, so a misconfigured gateway fails
# its readiness probe instead of crash-looping on import.
AGENT_IMAGE = os.environ.get("AGENT_IMAGE", "")

# The namespace where agent pods are created.  Namespaces are K8s's way of
# partitioning resources — like folders for your cluster objects.
AGENT_NAMESPACE = os.getenv("AGENT_NAMESPACE", "claude-agent")

# How many pre-warmed "standby" pods to keep ready.  When a user starts a
# session, we hand them one of these instead of creating a pod from scratch.
STANDBY_POOL_SIZE = int(os.getenv("STANDBY_POOL_SIZE", "2"))

# Handle for the background asyncio task that tops up the standby pool.
_replenish_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Pod manifest builder
# ---------------------------------------------------------------------------


def _build_pod_manifest(
    *,
    pod_name: str,
    labels: dict[str, str],
) -> client.V1Pod:
    """Build a V1Pod manifest for an agent pod.

    A V1Pod is the Python representation of a Kubernetes Pod spec.  It has two
    main sections:
      - metadata: name, namespace, labels (tags used for querying/filtering)
      - spec: the actual workload definition — containers, volumes, etc.

    V1Container describes the Docker container to run.  Important fields:
      - image: the container image to pull
      - env: environment variables injected into the container
      - volume_mounts: directories from K8s Volumes mapped into the container
      - resources: CPU/memory requests (scheduling hints) and limits (hard caps)
      - ports: which ports the container listens on

    Volumes are storage units attached to the pod.  Here we mount a K8s Secret
    as a read-only directory so the container can access TLS certificates
    without baking them into the image.
    """

    # --- Container definition ---
    container = client.V1Container(
        name="agent",
        image=AGENT_IMAGE,
        # IfNotPresent so kind-loaded images work.  A :latest tag implies
        # imagePullPolicy=Always by default, which would try to pull from a
        # registry and ignore the image kind already loaded onto the node.
        image_pull_policy="IfNotPresent",
        # The cookbook image's entrypoint defaults to a one-shot run; passing
        # "serve" starts the long-running FastAPI server (hosting/server.py).
        args=["serve"],
        env=[
            # Pull the API key from a K8s Secret.  Secrets store sensitive data
            # (passwords, tokens) and are base64-encoded at rest.  Using
            # secretKeyRef means the value is injected at pod start without
            # ever appearing in the pod spec itself.
            client.V1EnvVar(
                name="ANTHROPIC_API_KEY",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name="anthropic-api-key",
                        key="ANTHROPIC_API_KEY",
                    ),
                ),
            ),
            # Route API traffic through the egress proxy (a sidecar service
            # that handles TLS termination and outbound access control).
            client.V1EnvVar(
                name="ANTHROPIC_BASE_URL",
                value="https://egress-proxy",
            ),
            # Tell Node.js (and other tools) to trust the egress proxy's
            # self-signed CA certificate.
            client.V1EnvVar(
                name="NODE_EXTRA_CA_CERTS",
                value="/certs/ca.crt",
            ),
            # The port the agent's HTTP/WS server listens on inside the pod.
            client.V1EnvVar(
                name="PORT",
                value="8000",
            ),
            # Where the SDK writes session transcripts. Mounted as emptyDir
            # by default — see the README's Persistence section.
            client.V1EnvVar(
                name="CLAUDE_CONFIG_DIR",
                value="/data",
            ),
        ],
        # Mount the egress proxy's TLS certificate into /certs so the agent
        # can verify HTTPS connections through the proxy.
        volume_mounts=[
            client.V1VolumeMount(
                name="egress-proxy-tls",
                mount_path="/certs",
                read_only=True,
            ),
        ],
        # Resource requests and limits:
        # - "requests" tell the K8s scheduler how much capacity to reserve.
        #   The pod won't be placed on a node that can't satisfy these.
        # - "limits" are hard ceilings enforced by the kernel (via cgroups).
        #   If the container exceeds the memory limit it gets OOM-killed.
        resources=client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "2Gi"},
        ),
        # Declare that the container listens on port 8000.  This is mainly
        # documentation — K8s doesn't enforce it — but it helps tools and
        # other developers understand the pod's network interface.
        ports=[client.V1ContainerPort(container_port=8000)],
        # Readiness: a pod can be phase=Running while uvicorn is still
        # importing the SDK and hasn't bound port 8000 yet.  The gateway only
        # claims/routes to pods whose containers report Ready, so this probe
        # is what closes that gap.  (Kubelet probes come from the node, not a
        # pod, so the NetworkPolicy doesn't block them.)
        readiness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(path="/health", port=8000),
            initial_delay_seconds=2,
            period_seconds=2,
            failure_threshold=15,
        ),
        # Pod-level hardening for the container that runs model-driven code:
        # no privilege escalation, no Linux capabilities, and the default
        # seccomp filter (the same one Docker applies in Tier 1).
        # runAsNonRoot is intentionally NOT set — the shared Tier 1 image runs
        # as root; switching it to a non-root user is an image change, not a
        # manifest change.
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
        ),
    )

    # --- Pod definition ---
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=pod_name,
            namespace=AGENT_NAMESPACE,
            # Labels are arbitrary key/value pairs attached to the pod.
            # We use them to:
            #   - "app": identify pods belonging to this application
            #   - "role": distinguish agent pods from gateway/proxy pods
            #   - "pool-status": track standby vs. active lifecycle state
            #   - "session-id": link a pod to the user session that owns it
            labels=labels,
        ),
        spec=client.V1PodSpec(
            # The ServiceAccount controls what K8s API permissions the pod has.
            # "agent-sa" should be configured with minimal RBAC (the pod
            # doesn't need to talk to the K8s API at all).
            service_account_name="agent-sa",
            # The agent never calls the K8s API, so don't even mount the
            # service-account token — one less credential inside the pod that
            # runs model-driven code.
            automount_service_account_token=False,
            containers=[container],
            volumes=[
                # Make the "egress-proxy-tls" Secret available as a volume.
                # The Secret's data keys become files in the mount path.
                client.V1Volume(
                    name="egress-proxy-tls",
                    secret=client.V1SecretVolumeSource(
                        secret_name="egress-proxy-tls",  # noqa: S106 — k8s Secret name, not a credential
                    ),
                ),
            ],
            # "Never" means K8s won't restart the container if it exits.
            # Agent pods are ephemeral — one per session, deleted when done.
            restart_policy="Never",
            # uvicorn doesn't fast-exit on SIGTERM, so the default 30s grace
            # period just delays cleanup.  Agent pods hold no state worth
            # draining — 5s is plenty.
            termination_grace_period_seconds=5,
        ),
    )
    return pod


# ---------------------------------------------------------------------------
# Standby pool management
# ---------------------------------------------------------------------------


async def _create_standby_pod() -> str:
    """Create a single standby pod and return its name.

    Standby pods are pre-warmed: they pull the image, start the container,
    and sit idle waiting to be claimed by a session.  This means the user
    doesn't have to wait for image pull + container startup when they connect.
    """
    v1 = client.CoreV1Api()
    pod_name = f"agent-standby-{uuid.uuid4().hex[:8]}"
    labels = {
        "app": "claude-agent",
        "role": "agent",
        "pool-status": "standby",  # Not yet assigned to any session
    }
    pod_manifest = _build_pod_manifest(pod_name=pod_name, labels=labels)

    logger.info(f"Creating standby pod {pod_name}")
    # asyncio.to_thread() runs the blocking K8s client call in a thread-pool
    # worker so it doesn't block the async event loop.
    await asyncio.to_thread(
        v1.create_namespaced_pod,
        namespace=AGENT_NAMESPACE,
        body=pod_manifest,
    )
    return pod_name


def _pod_is_ready(pod) -> bool:
    """True when the pod is Running, has an IP, and all containers are Ready.

    "Running" only means the container process started; the readiness probe
    (an HTTP GET on /health) is what tells us uvicorn is actually listening.
    """
    return bool(
        pod.status.phase == "Running"
        and pod.status.pod_ip
        and pod.metadata.deletion_timestamp is None
        and all(cs.ready for cs in (pod.status.container_statuses or []))
    )


async def _wait_for_pod_running(pod_name: str, timeout: int = 120) -> str:
    """Poll a pod until it is Running *and* Ready.  Returns the pod IP.

    K8s pod phases: Pending -> Running -> Succeeded/Failed.
    We need to wait because the pod isn't usable until it's Running, has an
    IP address assigned by the cluster network, and its readiness probe
    confirms the agent server is accepting connections.

    Raises RuntimeError if the pod fails, TimeoutError if it doesn't start
    within `timeout` seconds.
    """
    v1 = client.CoreV1Api()
    interval = 2
    elapsed = 0

    while elapsed < timeout:
        pod = await asyncio.to_thread(
            v1.read_namespaced_pod,
            name=pod_name,
            namespace=AGENT_NAMESPACE,
        )
        phase = pod.status.phase
        logger.debug(f"Pod {pod_name} phase: {phase}")

        if _pod_is_ready(pod):
            logger.info(f"Pod {pod_name} ready at {pod.status.pod_ip}")
            return pod.status.pod_ip

        if phase in ("Failed", "Unknown"):
            raise RuntimeError(f"Pod {pod_name} entered {phase} state")

        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Pod {pod_name} did not become Ready within {timeout}s")


async def _get_standby_pods() -> list[str]:
    """Return names of standby pods that are Ready to serve a session.

    Uses a K8s label selector to filter — this is efficient because the API
    server does the filtering server-side rather than returning all pods.

    Two states are deliberately excluded: pods that are Terminating
    (deletionTimestamp set — claiming one routes the session to a container
    that's about to die) and pods that aren't Ready yet (uvicorn still
    starting — claiming one gets a connection error).
    """
    v1 = client.CoreV1Api()
    pods = await asyncio.to_thread(
        v1.list_namespaced_pod,
        namespace=AGENT_NAMESPACE,
        label_selector="role=agent,pool-status=standby",
    )
    return [p.metadata.name for p in pods.items if _pod_is_ready(p)]


async def _count_standby_pods() -> int:
    """Count standby pods that exist or are on their way (Pending or Running).

    Used when deciding whether to create more.  Unlike ``_get_standby_pods``
    (which only returns *claimable* pods), this counts Pending pods too —
    on a cold cluster they're still pulling the image, and not counting them
    would make the replenisher over-provision.
    """
    v1 = client.CoreV1Api()
    pods = await asyncio.to_thread(
        v1.list_namespaced_pod,
        namespace=AGENT_NAMESPACE,
        label_selector="role=agent,pool-status=standby",
    )
    return sum(
        1
        for p in pods.items
        if p.status.phase in ("Pending", "Running") and p.metadata.deletion_timestamp is None
    )


async def _delete_pod_by_name(pod_name: str) -> None:
    """Delete a single pod by name, ignoring 404s."""
    v1 = client.CoreV1Api()
    try:
        await asyncio.to_thread(
            v1.delete_namespaced_pod,
            name=pod_name,
            namespace=AGENT_NAMESPACE,
        )
    except kubernetes.client.exceptions.ApiException as e:
        if e.status != 404:
            raise


async def _claim_standby_pod(session_id: str) -> str | None:
    """Try to atomically claim a standby pod for a session.  Returns pod IP or None.

    Uses JSON Patch with a 'test' operation to assert pool-status=standby before
    claiming. If another gateway instance claims the same pod concurrently, the
    test assertion fails and the API returns 409/422 — the loser skips to the
    next standby pod. This provides compare-and-swap semantics without external
    locking.

    Strategic-merge-patch (the default for dict bodies) is last-writer-wins and
    cannot detect concurrent claims — both gateways would succeed, routing two
    sessions to one pod (CWE-362 / CWE-863).
    """
    v1 = client.CoreV1Api()
    standby_pods = await _get_standby_pods()

    for pod_name in standby_pods:
        try:
            # JSON Patch: first assert pool-status is still 'standby' (test op),
            # then flip it to 'active' and stamp session-id.  If another gateway
            # already claimed this pod the test fails → K8s returns 409/422 and
            # we move on to the next standby pod instead of double-routing.
            patch_ops = [
                {"op": "test", "path": "/metadata/labels/pool-status", "value": "standby"},
                {"op": "replace", "path": "/metadata/labels/pool-status", "value": "active"},
                {"op": "add", "path": "/metadata/labels/session-id", "value": str(session_id)},
            ]
            patched = await asyncio.to_thread(
                v1.patch_namespaced_pod,
                name=pod_name,
                namespace=AGENT_NAMESPACE,
                body=patch_ops,
                content_type="application/json-patch+json",
            )
            pod_ip = patched.status.pod_ip
            logger.info(f"Claimed standby pod {pod_name} for session {session_id} at {pod_ip}")
            return pod_ip
        except kubernetes.client.exceptions.ApiException as e:
            if e.status in (409, 422):
                # Test op failed: pod was already claimed by another gateway.
                logger.debug(f"Pod {pod_name} already claimed (HTTP {e.status}), trying next")
            else:
                logger.warning(f"Failed to claim pod {pod_name}: {e.status}")
            continue

    return None


async def _replenish_pool() -> None:
    """Top up the standby pool to STANDBY_POOL_SIZE.

    Called after a pod is claimed or deleted.  Creates pods one at a time
    and re-counts the pool before each one, so claims that happen *while*
    we're replenishing are picked up by this run instead of waiting for the
    next trigger.  The count includes Pending pods so a slow image pull
    doesn't cause over-provisioning.

    The loop is bounded so a persistently failing image (bad tag, missing
    secret) can't spin forever; it bails out on the first failed pod after
    cleaning it up.
    """
    for _ in range(STANDBY_POOL_SIZE * 2):
        current_count = await _count_standby_pods()
        if current_count >= STANDBY_POOL_SIZE:
            logger.debug(
                f"Standby pool has {current_count}/{STANDBY_POOL_SIZE} pods, "
                "no replenishment needed"
            )
            return

        logger.info(
            f"Replenishing standby pool: {current_count}/{STANDBY_POOL_SIZE}, creating 1 pod"
        )
        pod_name = None
        try:
            pod_name = await _create_standby_pod()
            # Wait for the pod to be Running before counting it as ready
            await _wait_for_pod_running(pod_name)
        except Exception:
            logger.exception("Failed to create standby pod")
            if pod_name:
                # Don't leave a Failed/stuck pod labeled "standby" behind —
                # it would count toward the pool but never serve a session.
                try:
                    await _delete_pod_by_name(pod_name)
                except Exception:
                    logger.exception(f"Could not clean up failed standby pod {pod_name}")
            return


def _schedule_replenish() -> None:
    """Kick off pool replenishment as a background asyncio task.

    This is fire-and-forget — the caller doesn't wait for replenishment to
    finish.  If replenishment is already running, this is a no-op to avoid
    duplicate work.
    """
    global _replenish_task
    if _replenish_task and not _replenish_task.done():
        return  # Already replenishing
    try:
        loop = asyncio.get_running_loop()
        _replenish_task = loop.create_task(_replenish_pool())
    except RuntimeError:
        logger.warning("No running event loop, skipping replenishment")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def initialize_standby_pool() -> None:
    """Pre-warm the standby pool on gateway startup.

    Called once during application boot.  If K8s is unavailable (e.g. local
    dev), this is a no-op.
    """
    if not _k8s_available:
        logger.info("K8s unavailable — skipping standby pool initialization")
        return
    if not AGENT_IMAGE:
        raise RuntimeError("AGENT_IMAGE env var is required when running inside Kubernetes")
    logger.info(f"Initializing standby pool with {STANDBY_POOL_SIZE} pods")
    await _replenish_pool()


async def create_agent_pod(session_id: str) -> str:
    """Get a running agent pod for a session.  Returns the pod IP address.

    Strategy:
    1. Try to claim a pre-warmed standby pod (instant).
    2. If none available, create an on-demand pod (slower — has to pull image).

    Either way, replenish the pool in the background afterwards so the next
    session will (hopefully) get a standby pod.
    """
    # Try to claim a pre-warmed standby pod first
    pod_ip = await _claim_standby_pod(session_id)
    if pod_ip:
        _schedule_replenish()
        return pod_ip

    # No standby pods available — fall back to creating one on-demand
    logger.warning(f"No standby pods available for session {session_id}, creating on-demand")
    pod_name = f"agent-session-{session_id}"
    labels = {
        "app": "claude-agent",
        "role": "agent",
        "pool-status": "active",
        "session-id": str(session_id),
    }
    pod_manifest = _build_pod_manifest(pod_name=pod_name, labels=labels)

    v1 = client.CoreV1Api()
    await asyncio.to_thread(
        v1.create_namespaced_pod,
        namespace=AGENT_NAMESPACE,
        body=pod_manifest,
    )

    pod_ip = await _wait_for_pod_running(pod_name)
    _schedule_replenish()
    return pod_ip


async def delete_agent_pod(session_id: str) -> None:
    """Delete the agent pod for a session.

    Searches by label first (works for both claimed standby and on-demand pods),
    then falls back to the conventional name as a safety net.
    """
    v1 = client.CoreV1Api()

    # Find pod by session-id label (works for both claimed standby and
    # on-demand pods, since both get the session-id label).
    pods = await asyncio.to_thread(
        v1.list_namespaced_pod,
        namespace=AGENT_NAMESPACE,
        label_selector=f"role=agent,session-id={session_id}",
    )

    if not pods.items:
        # Fallback: try the deterministic name used for on-demand pods
        pod_name = f"agent-session-{session_id}"
        try:
            await asyncio.to_thread(
                v1.delete_namespaced_pod,
                name=pod_name,
                namespace=AGENT_NAMESPACE,
            )
            logger.info(f"Deleted pod {pod_name}")
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.debug(f"No pod found for session {session_id}")
            else:
                raise
        return

    for pod in pods.items:
        pod_name = pod.metadata.name
        try:
            await asyncio.to_thread(
                v1.delete_namespaced_pod,
                name=pod_name,
                namespace=AGENT_NAMESPACE,
            )
            logger.info(f"Deleted pod {pod_name} for session {session_id}")
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 404:
                logger.debug(f"Pod {pod_name} already gone")
            else:
                raise

    # Replenish pool after freeing a slot
    _schedule_replenish()


async def get_pool_status() -> dict:
    """Return the current state of the standby pool.

    Useful for health checks and debugging — tells you how many standby
    pods are ready vs. the target pool size.
    """
    standby_pods = await _get_standby_pods()
    return {
        "target_size": STANDBY_POOL_SIZE,
        "ready_count": len(standby_pods),
        "standby_pods": standby_pods,
    }

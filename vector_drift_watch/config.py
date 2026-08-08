"""Defaults for the demo corpus, fixed query set, and alert thresholds.

Everything here is overridable from the CLI; these are just what the demo
and docker-compose setup use out of the box.
"""

from __future__ import annotations

import os

DEFAULT_DATABASE_URL = os.environ.get(
    "VECTOR_DRIFT_WATCH_DATABASE_URL",
    "postgresql://vdw:vdw@localhost:5432/vdw",
)
DEFAULT_EMBEDDING_DIMENSION = 128
DEFAULT_LATENCY_P95_THRESHOLD_MS = 50.0
DEFAULT_DRIFT_THRESHOLD = 0.15

# A small runbook-style corpus, stand-in for a real AI/ML platform's
# internal docs, used to give the demo something realistic to query against.
DEMO_CORPUS: dict[str, str] = {
    "doc-gpu-drain": (
        "To drain a GPU node before maintenance, cordon it first so the scheduler "
        "stops placing new Ray workers there, then evict running actors with a "
        "grace period long enough for in flight batches to finish."
    ),
    "doc-model-serve-timeout": (
        "Model serving requests that exceed the p99 latency budget usually trace "
        "back to cold starts on autoscaled replicas or a vector store query that "
        "regressed after an index rebuild."
    ),
    "doc-embedding-drift": (
        "Embedding drift shows up as a steady increase in cosine distance between "
        "a fixed query set's embeddings captured at different times, often caused "
        "by an unannounced model version bump upstream."
    ),
    "doc-vector-store-latency": (
        "Vector store p95 latency should stay flat as the index grows if it is "
        "using an approximate nearest neighbor index; a linear climb usually means "
        "the index fell back to a sequential scan."
    ),
    "doc-rag-retrieval-quality": (
        "A RAG pipeline's answer quality degrades silently when retrieval starts "
        "returning stale chunks, which is why retrieval latency and embedding "
        "drift need to be watched together, not separately."
    ),
    "doc-pagerduty-escalation": (
        "Alerts that fire on a single threshold breach without confirming a second "
        "sample tend to page on noise; require two consecutive probe cycles over "
        "threshold before escalating to PagerDuty."
    ),
    "doc-multicloud-node-labels": (
        "AWS EKS and GCP GKE label their nodes differently: EKS uses "
        "eks.amazonaws.com/nodegroup while GKE uses cloud.google.com/gke-nodepool, "
        "so any cross cloud automation needs a small adapter layer."
    ),
    "doc-self-healing-controller": (
        "A self healing controller should count consecutive failures before taking "
        "action, not react to the first failed health check, or it will restart "
        "healthy pods during a brief network blip."
    ),
}

# Fixed query set probed for both latency and drift. Keeping this fixed is
# what makes drift comparisons meaningful across snapshots.
DEMO_QUERIES: list[str] = [
    "how do I drain a gpu node safely",
    "why is model serving timing out",
    "what does embedding drift look like",
    "why did vector store latency spike",
    "how do I detect stale rag retrieval",
    "how many failures before paging on call",
]

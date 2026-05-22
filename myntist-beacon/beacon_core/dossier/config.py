"""
IP Dossier feature-flag configuration.

The IP Dossier feature enriches incoming POST /events requests with IP reputation
data (ASN, country, threat score) from a configurable provider. It is a Phase 3
capability and is **disabled by default** to avoid adding latency or external
dependencies to the current ECS deployment.

Enable by setting IP_DOSSIER_ENABLED=true in the environment (or SSM) and
configuring IP_DOSSIER_PROVIDER_URL and IP_DOSSIER_API_KEY.

Usage:
    from beacon_core.dossier.config import DOSSIER_ENABLED

    if DOSSIER_ENABLED:
        from beacon_core.dossier.enricher import enrich_request
        dossier = enrich_request(client_ip)
"""
from __future__ import annotations

import os

# Master feature flag — set IP_DOSSIER_ENABLED=true to activate
DOSSIER_ENABLED: bool = os.getenv("IP_DOSSIER_ENABLED", "false").lower() == "true"

# Provider endpoint and credentials (only required when DOSSIER_ENABLED=true)
DOSSIER_PROVIDER_URL: str = os.getenv(
    "IP_DOSSIER_PROVIDER_URL", "https://api.ipinfo.io"
)
DOSSIER_API_KEY: str = os.getenv("IP_DOSSIER_API_KEY", "")

# Maximum seconds to wait for the dossier provider before giving up.
# Keep this low so a slow/offline provider does not block event ingestion.
DOSSIER_TIMEOUT_SECONDS: float = float(os.getenv("IP_DOSSIER_TIMEOUT", "2.0"))

# When set, block events whose threat score exceeds this threshold (0.0 – 1.0).
# Leave empty to run in enrichment-only mode (no blocking).
DOSSIER_BLOCK_THRESHOLD: float | None = (
    float(os.getenv("IP_DOSSIER_BLOCK_THRESHOLD"))
    if os.getenv("IP_DOSSIER_BLOCK_THRESHOLD")
    else None
)

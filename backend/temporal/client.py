from __future__ import annotations

import logging
import os

from temporalio.client import Client

logger = logging.getLogger(__name__)


async def get_temporal_client() -> Client:
    """Create a Temporal client using environment-backed connection settings.

    Args:
        None

    Returns:
        Connected Temporal client.
    """
    target_host = os.environ["TEMPORAL_SERVER_ADDRESS"]
    namespace = os.environ["TEMPORAL_NAMESPACE"]
    logger.info(f"Temporal client connect target_host={target_host} namespace={namespace}")
    return await Client.connect(target_host=target_host, namespace=namespace)


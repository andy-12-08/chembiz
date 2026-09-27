from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure process-wide logging for local and container visibility.

    The LOG_LEVEL environment variable selects the threshold and defaults to
    INFO when it is absent or invalid. Existing root handlers are replaced so
    repeated initialization uses one consistent format.

    Returns:
        None.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )

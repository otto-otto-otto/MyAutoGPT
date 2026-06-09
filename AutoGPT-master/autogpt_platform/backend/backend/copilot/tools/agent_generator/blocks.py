"""Block cache invalidation — companion to ``optimize_blocks``."""

import logging

logger = logging.getLogger(__name__)


def reset_block_caches() -> None:
    """Clear any in-memory block metadata caches (no-op stub)."""
    logger.debug("Block caches reset (no-op)")

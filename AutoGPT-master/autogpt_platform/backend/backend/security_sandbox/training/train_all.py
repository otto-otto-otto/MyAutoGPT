"""
Orchestration entry point for training all security sandbox models.

Usage:
    python -m backend.security_sandbox.training.train_all

Called during Docker build (model-trainer stage) to pre-train models.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from .train_sensitive_word import train_sensitive_word_model
from .train_code_security import train_code_security_model

logger = logging.getLogger(__name__)


def train_all_models(output_dir: str | None = None) -> dict:
    """
    Train all security sandbox models and save to output_dir.

    Returns combined training summary.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "models")

    os.makedirs(output_dir, exist_ok=True)

    results = {}

    # Train sensitive word model
    logger.info("=" * 60)
    logger.info("Training SENSITIVE WORD detection model...")
    logger.info("=" * 60)
    sw_result = train_sensitive_word_model(output_dir=output_dir)
    results["sensitive_word"] = sw_result

    # Train code security model
    logger.info("=" * 60)
    logger.info("Training CODE SECURITY detection model...")
    logger.info("=" * 60)
    cs_result = train_code_security_model(output_dir=output_dir)
    results["code_security"] = cs_result

    # Write combined summary
    summary = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "models": results,
        "output_directory": output_dir,
    }
    summary_path = os.path.join(output_dir, "model_metadata.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info("All models trained successfully!")
    logger.info(f"Sensitive word accuracy: {results['sensitive_word']['accuracy']}")
    logger.info(f"Code security accuracy: {results['code_security']['accuracy']}")
    logger.info(f"Models saved to: {output_dir}")
    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    train_all_models()

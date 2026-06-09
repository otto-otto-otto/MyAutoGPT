"""
Training datasets for security sandbox ML models.

IMPORTANT: This module does NOT contain hardcoded sensitive word lists.
Instead, it uses statistical feature engineering and multi-category
risk-pattern corpora for model training.
"""

from .sensitive_words_dataset import (
    FEATURE_NAMES_V2,
    RISK_CATEGORIES,
    generate_sensitive_word_dataset,
    get_risk_samples_by_category,
    SENSITIVE_WORD_FEATURE_CONFIG,
)
from .code_security_dataset import (
    generate_code_security_dataset,
    CODE_SECURITY_PATTERN_CONFIG,
)

__all__ = [
    "generate_sensitive_word_dataset",
    "generate_code_security_dataset",
    "get_risk_samples_by_category",
    "SENSITIVE_WORD_FEATURE_CONFIG",
    "CODE_SECURITY_PATTERN_CONFIG",
    "FEATURE_NAMES_V2",
    "RISK_CATEGORIES",
]

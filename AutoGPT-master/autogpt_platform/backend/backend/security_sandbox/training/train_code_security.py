"""
Train a code security detection model using rule-based features + TF-IDF + LR.

Feature strategy:
  - Regex pattern matching against known dangerous code patterns
  - TF-IDF on tokenized code (simple whitespace tokenization)
  - Combined features for classification

Output:
  - cs_model.pkl: joblib dump of (vectorizer, scaler, classifier, patterns)
  - cs_model_metadata.json: accuracy, pattern coverage, timestamp
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .dataset.code_security_dataset import (
    CODE_SECURITY_PATTERN_CONFIG,
    generate_code_security_dataset,
)

logger = logging.getLogger(__name__)


def _simple_tokenizer(text: str) -> str:
    """Simple whitespace + punctuation tokenizer for code."""
    import re
    tokens = re.findall(r"[a-zA-Z_]\w*|[0-9]+|[^\s\w]", text)
    return " ".join(tokens)


def train_code_security_model(
    output_dir: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """
    Train the code security detection model.

    Args:
        output_dir: Directory to save model files
        test_size: Proportion of data for testing
        random_state: Random seed

    Returns:
        dict with training metrics
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "models")

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Loading code security training dataset...")
    dataset = generate_code_security_dataset()
    codes = [item["code"] for item in dataset]
    labels = np.array([item["label"] for item in dataset])

    logger.info(f"Dataset size: {len(codes)} samples (class 0: {(labels == 0).sum()}, class 1: {(labels == 1).sum()})")

    # Split data
    X_train_codes, X_test_codes, y_train, y_test = train_test_split(
        codes, labels, test_size=test_size, random_state=random_state, stratify=labels
    )

    # TF-IDF vectorization for code tokens
    logger.info("Fitting code TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(
        tokenizer=_simple_tokenizer,
        max_features=2000,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train_codes)
    X_test_tfidf = vectorizer.transform(X_test_codes)

    # Extract rule-based pattern features
    logger.info("Extracting rule-based pattern features...")
    train_dataset_slice = [item for item in dataset[: len(X_train_codes)]]
    test_dataset_slice = [item for item in dataset[len(X_train_codes):]]

    def _pattern_features(items):
        features = []
        for item in items:
            feats = []
            for category in CODE_SECURITY_PATTERN_CONFIG:
                feats.append(item["features"].get(f"pattern_{category}", 0))
            features.append(feats)
        return np.array(features, dtype=float)

    train_pattern_features = _pattern_features(train_dataset_slice)
    test_pattern_features = _pattern_features(test_dataset_slice)

    # Combine TF-IDF with rule-based features
    from scipy.sparse import hstack as sparse_hstack
    X_train = sparse_hstack([X_train_tfidf, train_pattern_features])
    X_test = sparse_hstack([X_test_tfidf, test_pattern_features])

    # Scale
    scaler = StandardScaler(with_mean=False)
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train classifier
    logger.info("Training Logistic Regression classifier for code security...")
    classifier = LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=random_state,
        solver="liblinear",
    )
    classifier.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = classifier.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=["safe", "dangerous"], output_dict=True)

    logger.info(f"Model accuracy: {accuracy:.4f}")
    logger.info(f"Classification report:\n{classification_report(y_test, y_pred, target_names=['safe', 'dangerous'])}")

    # Save model bundle
    model_bundle = {
        "vectorizer": vectorizer,
        "scaler": scaler,
        "classifier": classifier,
        "patterns": CODE_SECURITY_PATTERN_CONFIG,
    }
    model_path = os.path.join(output_dir, "cs_model.pkl")
    joblib.dump(model_bundle, model_path, compress=3)
    logger.info(f"Model saved to {model_path}")

    # Save metadata
    metadata = {
        "model_type": "code_security_detection",
        "algorithm": "TF-IDF + Rule Features + LogisticRegression",
        "accuracy": round(accuracy, 4),
        "f1_score_dangerous": round(report["dangerous"]["f1-score"], 4),
        "precision_dangerous": round(report["dangerous"]["precision"], 4),
        "recall_dangerous": round(report["dangerous"]["recall"], 4),
        "training_samples": len(codes),
        "class_distribution": {"safe": int((labels == 0).sum()), "dangerous": int((labels == 1).sum())},
        "rule_categories": list(CODE_SECURITY_PATTERN_CONFIG.keys()),
        "feature_count": X_train_tfidf.shape[1] + train_pattern_features.shape[1],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }
    metadata_path = os.path.join(output_dir, "cs_model_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    logger.info(f"Metadata saved to {metadata_path}")

    return metadata


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = train_code_security_model()
    print(f"\nTraining complete. Accuracy: {result['accuracy']}")

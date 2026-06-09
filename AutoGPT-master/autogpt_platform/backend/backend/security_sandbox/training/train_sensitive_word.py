"""
Train a TF-IDF + Logistic Regression model for sensitive/risky text detection (v2.0).

Feature extraction strategy (v2 — 11 numerical features):
  - TF-IDF vectorization on Chinese text (with jieba tokenization)
  - 11 additional statistical features (entropy, density ratios, flags)
  - Combined feature vector for classifier training

Output:
  - sw_model.pkl: joblib dump of (vectorizer, scaler, classifier)
  - sw_model_metadata.json: accuracy, class distribution, timestamp
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

import joblib
import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .dataset.sensitive_words_dataset import (
    FEATURE_NAMES_V2,
    generate_sensitive_word_dataset,
)

logger = logging.getLogger(__name__)


def _jieba_tokenizer(text: str) -> str:
    """Custom tokenizer using jieba for Chinese text segmentation."""
    return " ".join(jieba.cut(text))


def train_sensitive_word_model(
    output_dir: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """
    Train the sensitive word detection model (v2).

    Uses 11 enhanced statistical features + TF-IDF vectors.

    Args:
        output_dir: Directory to save model files. Defaults to ../models/
        test_size: Proportion of data used for testing
        random_state: Random seed for reproducibility

    Returns:
        dict with training metrics
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "models")

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Loading sensitive word training dataset (v2 multi-category)...")
    dataset = generate_sensitive_word_dataset()
    texts = [item["text"] for item in dataset]
    labels = np.array([item["label"] for item in dataset])

    # Per-category stats
    category_counts: dict[str, int] = {}
    for item in dataset:
        cat = item.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    logger.info(
        f"Dataset: {len(texts)} samples "
        f"(benign: {(labels == 0).sum()}, risk: {(labels == 1).sum()})"
    )
    logger.info(f"Category distribution: {category_counts}")

    # Split data
    indices = np.arange(len(dataset))
    train_idx, test_idx = train_test_split(
        indices, test_size=test_size, random_state=random_state, stratify=labels
    )

    X_train_texts = [texts[i] for i in train_idx]
    X_test_texts = [texts[i] for i in test_idx]
    y_train = labels[train_idx]
    y_test = labels[test_idx]

    # ---- TF-IDF vectorization ----
    logger.info("Fitting TF-IDF vectorizer with jieba tokenizer...")
    vectorizer = TfidfVectorizer(
        tokenizer=_jieba_tokenizer,
        max_features=5000,
        ngram_range=(1, 3),
        min_df=2,
        max_df=0.9,
        sublinear_tf=True,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train_texts)
    X_test_tfidf = vectorizer.transform(X_test_texts)
    logger.info(f"TF-IDF vocabulary size: {len(vectorizer.vocabulary_)}")

    # ---- Statistical features (v2 — 11 features) ----
    logger.info(f"Extracting {len(FEATURE_NAMES_V2)} statistical features...")

    def _features_for_indices(indices_list: np.ndarray) -> np.ndarray:
        feats = []
        for idx in indices_list:
            feat_dict = dataset[idx]["features"]
            feats.append([feat_dict[name] for name in FEATURE_NAMES_V2])
        return np.array(feats)

    train_features = _features_for_indices(train_idx)
    test_features = _features_for_indices(test_idx)

    # ---- Combine TF-IDF + statistical features ----
    from scipy.sparse import hstack as sparse_hstack
    X_train = sparse_hstack([X_train_tfidf, train_features])
    X_test = sparse_hstack([X_test_tfidf, test_features])

    # ---- Scale ----
    scaler = StandardScaler(with_mean=False)  # sparse matrices
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ---- Train classifier ----
    logger.info("Training Logistic Regression classifier (v2)...")
    classifier = LogisticRegression(
        C=0.8,
        max_iter=2000,
        class_weight="balanced",
        random_state=random_state,
        solver="liblinear",
        penalty="l2",
    )
    classifier.fit(X_train_scaled, y_train)

    # ---- Evaluate ----
    y_pred = classifier.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=["benign", "risk"],
        output_dict=True,
    )

    logger.info(f"Model accuracy: {accuracy:.4f}")
    logger.info(
        "Classification report:\n"
        f"{classification_report(y_test, y_pred, target_names=['benign', 'risk'])}"
    )

    # ---- Save model bundle ----
    model_bundle = {
        "vectorizer": vectorizer,
        "scaler": scaler,
        "classifier": classifier,
        "feature_names": FEATURE_NAMES_V2,
        "model_version": "2.0.0",
    }
    model_path = os.path.join(output_dir, "sw_model.pkl")
    joblib.dump(model_bundle, model_path, compress=3)
    logger.info(f"Model saved to {model_path}")

    # ---- Save metadata ----
    metadata = {
        "model_type": "sensitive_word_detection_v2",
        "algorithm": "TF-IDF + LogisticRegression",
        "tokenizer": "jieba",
        "accuracy": round(accuracy, 4),
        "f1_score_risk": round(report["risk"]["f1-score"], 4),
        "precision_risk": round(report["risk"]["precision"], 4),
        "recall_risk": round(report["risk"]["recall"], 4),
        "training_samples": len(texts),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "class_distribution": {
            "benign": int((labels == 0).sum()),
            "risk": int((labels == 1).sum()),
        },
        "category_distribution": category_counts,
        "feature_count": X_train_tfidf.shape[1] + len(FEATURE_NAMES_V2),
        "statistical_features": FEATURE_NAMES_V2,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
    }
    metadata_path = os.path.join(output_dir, "sw_model_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    logger.info(f"Metadata saved to {metadata_path}")

    return metadata


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    result = train_sensitive_word_model()
    print(f"\nTraining complete. v{result['version']} | Accuracy: {result['accuracy']}")

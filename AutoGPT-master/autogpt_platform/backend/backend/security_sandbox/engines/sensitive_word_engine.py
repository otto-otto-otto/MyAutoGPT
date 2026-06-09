"""
Sensitive word / risky content detection engine (v2.0).

Three-layer detection architecture:
  1. External rules config   — user-supplied keyword lists (fastest)
  2. Statistical rule checks  — anomaly patterns (entropy, density)
  3. ML model prediction      — TF-IDF + LogisticRegression (trained)

Covered risk categories:
  - phishing, fraud, spam, gambling-bait, aggressive-marketing,
    contact-solicitation (via ML + built-in rules)
  - User-extensible via `sensitive_rules_config.json` for domain terms
    (porn, violence, gambling keywords, etc.)
"""

import json
import logging
import math
import os
import re
from collections import Counter
from typing import Any

import joblib
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature extraction patterns (mirrors dataset)
# ---------------------------------------------------------------------------

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    re.UNICODE,
)

_CONTACT_PATTERN = re.compile(
    r"(?:"
    r"1[3-9]\d{9}"
    r"|\d{3,4}[-]?\d{7,8}"
    r"|[qQ]{2}\s*\d{5,}"
    r"|[vVxX]\s*\w{5,}"
    r"|微信\s*\w{2,}"
    r"|加\s*(?:我|微信|QQ)"
    r"|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    r")"
)

_HOMOGLYPH_PATTERN = re.compile(
    "["
    "\U00000400-\U000004FF"
    "\U0000FF00-\U0000FFEF"
    "\U0000FE00-\U0000FE0F"
    "\U0000200B-\U0000200F"
    "\U0000FEFF"
    "\U00002061-\U00002064"
    "]+",
    re.UNICODE,
)

FEATURE_NAMES_V2 = [
    "entropy",
    "punctuation_ratio",
    "digit_ratio",
    "special_char_ratio",
    "repeated_char_ratio",
    "url_flag",
    "contact_info_flag",
    "emoji_ratio",
    "exclamation_ratio",
    "consecutive_repeat_max",
    "homoglyph_flag",
]


# ---------------------------------------------------------------------------
# Engine result
# ---------------------------------------------------------------------------

class EngineResult:
    """Result from the sensitive-word engine's prediction."""

    __slots__ = ("decision", "score", "matches", "reason", "categories")

    def __init__(
        self,
        decision: str,
        score: float,
        matches: list[str],
        reason: str,
        categories: list[str] | None = None,
    ):
        self.decision = decision    # "approved", "rejected", or "flagged"
        self.score = score
        self.matches = matches      # matched warning/category tags
        self.reason = reason
        self.categories = categories or []  # which risk categories triggered

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "score": self.score,
            "matches": self.matches,
            "reason": self.reason,
            "categories": self.categories,
        }


# ---------------------------------------------------------------------------
# SensitiveWordEngine v2
# ---------------------------------------------------------------------------

class SensitiveWordEngine:
    """
    Sensitive/risky content detection engine (v2).

    Combines:
      - External keyword rules (user-configurable JSON)
      - Built-in statistical rule checks
      - ML model (TF-IDF + LogisticRegression)
    """

    HIGH_RISK_THRESHOLD = 0.75
    LOW_RISK_THRESHOLD = 0.35

    def __init__(self):
        self._model_bundle: dict | None = None
        self._loaded = False
        self._version: str = "unknown"

        # External rules config
        self._rules_config: dict | None = None
        self._rules_loaded = False
        self._rules_path: str = ""

        # Compiled regexes from external rules
        self._compiled_category_rules: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def rules_loaded(self) -> bool:
        return self._rules_loaded

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self, model_path: str) -> bool:
        """Load pre-trained ML model from .pkl file."""
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return False

        self._model_bundle = joblib.load(model_path)
        self._loaded = True

        meta_path = model_path.replace(".pkl", "_metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self._version = meta.get("version", "unknown")

        logger.info(f"SensitiveWordEngine model loaded (v{self._version})")

        # Try loading companion rules config
        model_dir = os.path.dirname(model_path)
        rules_path = os.path.join(model_dir, "sensitive_rules_config.json")
        if os.path.exists(rules_path):
            self.load_rules_config(rules_path)

        return True

    # ------------------------------------------------------------------
    # External rules config
    # ------------------------------------------------------------------

    def load_rules_config(self, config_path: str) -> bool:
        """
        Load user-supplied keyword rules from a JSON config file.

        Expected JSON structure — see sensitive_rules_config.example.json:
          {
            "categories": {
              "<name>": {
                "enabled": true,
                "action": "reject" | "flag",
                "terms": ["term1", "term2", ...],
                "patterns": ["regex1", "regex2", ...]
              },
              ...
            },
            "global_settings": { "min_match_length": 2, "case_sensitive": false }
          }

        Returns True if loaded successfully.
        """
        if not os.path.exists(config_path):
            logger.info(f"No external rules config at {config_path} — skipping")
            return False

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._rules_config = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to parse rules config: {exc}")
            return False

        # Compile category rules
        self._compiled_category_rules = {}
        categories = self._rules_config.get("categories", {})
        global_settings = self._rules_config.get("global_settings", {})
        case_sensitive = global_settings.get("case_sensitive", False)

        for cat_name, cat_cfg in categories.items():
            if not cat_cfg.get("enabled", True):
                continue

            terms = cat_cfg.get("terms", [])
            patterns = cat_cfg.get("patterns", [])
            action = cat_cfg.get("action", "flag")

            # Pre-compile regex patterns
            compiled_patterns = []
            for pat in patterns:
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    compiled_patterns.append(re.compile(pat, flags))
                except re.error as exc:
                    logger.warning(f"Invalid regex in category '{cat_name}': {exc}")

            # Prepare normalized search terms
            search_terms = terms if case_sensitive else [t.lower() for t in terms]

            self._compiled_category_rules[cat_name] = {
                "action": action,
                "terms": search_terms,
                "patterns": compiled_patterns,
                "case_sensitive": case_sensitive,
            }

        self._rules_loaded = True
        self._rules_path = config_path
        logger.info(
            f"External rules loaded: {len(self._compiled_category_rules)} "
            f"active categories from {config_path}"
        )
        return True

    # ------------------------------------------------------------------
    # Feature extraction (mirrors training pipeline)
    # ------------------------------------------------------------------

    def _extract_features(self, text: str) -> dict[str, float]:
        """Extract enhanced statistical features (v2)."""
        if not text:
            return {name: 0.0 for name in FEATURE_NAMES_V2}

        chars = list(text)
        n = len(chars)

        char_counts = Counter(chars)
        entropy = -sum(
            (c / n) * math.log2(c / n) for c in char_counts.values() if c > 0
        )

        punctuation_set = set(',.!?;:、，。！？；：""''（）【】《》…—～')
        punctuation = sum(1 for ch in chars if ch in punctuation_set)
        digits = sum(1 for ch in chars if ch.isdigit())
        special_chars = sum(1 for ch in chars if ch in '@#$%^&*+=|\\/<>[]{}~`')

        repeated = sum(
            1 for i in range(1, n) if chars[i] == chars[i - 1]
        ) / max(n, 1)

        max_consecutive = 1
        current_run = 1
        for i in range(1, n):
            if chars[i] == chars[i - 1]:
                current_run += 1
                max_consecutive = max(max_consecutive, current_run)
            else:
                current_run = 1

        url_flag = 1 if any(
            m in text for m in ['http', 'www.', '.com', '.cn', '.net', '链接', '点击']
        ) else 0

        contact_flag = 1 if _CONTACT_PATTERN.search(text) else 0

        emoji_matches = _EMOJI_PATTERN.findall(text)
        emoji_chars = sum(len(m) for m in emoji_matches)
        emoji_ratio = emoji_chars / max(n, 1)

        exclamation = sum(1 for ch in chars if ch in '!！')
        exclamation_ratio = exclamation / max(n, 1)

        homoglyph_flag = 1 if _HOMOGLYPH_PATTERN.search(text) else 0

        return {
            "entropy": round(entropy, 4),
            "punctuation_ratio": round(punctuation / max(n, 1), 4),
            "digit_ratio": round(digits / max(n, 1), 4),
            "special_char_ratio": round(special_chars / max(n, 1), 4),
            "repeated_char_ratio": round(repeated, 4),
            "url_flag": url_flag,
            "contact_info_flag": contact_flag,
            "emoji_ratio": round(emoji_ratio, 4),
            "exclamation_ratio": round(exclamation_ratio, 4),
            "consecutive_repeat_max": max_consecutive,
            "homoglyph_flag": homoglyph_flag,
        }

    # ------------------------------------------------------------------
    # Rule-based checks
    # ------------------------------------------------------------------

    def _rule_based_check(self, text: str) -> list[str]:
        """Enhanced rule-based pre-check (v2)."""
        warnings: list[str] = []

        # ---- Excessive repetition ----
        if len(text) > 10:
            char_freq = Counter(text)
            if char_freq.most_common(1)[0][1] / len(text) > 0.5:
                warnings.append("excessive_character_repetition")

        # ---- URL in short text ----
        url_count = len(re.findall(r'https?://|www\.|\.com|\.cn|\.net', text))
        if url_count > 0 and len(text) < 200:
            warnings.append("url_in_short_text")

        # ---- All-caps ----
        if any(c.isalpha() for c in text):
            upper = sum(1 for c in text if c.isupper())
            alpha = sum(1 for c in text if c.isalpha())
            if alpha > 0 and upper / alpha > 0.7:
                warnings.append("excessive_uppercase")

        # ---- Newline injection ----
        if text.count('\n') > 5 and len(text) < 500:
            warnings.append("excessive_newlines")

        # ---- Contact info solicitation ----
        if _CONTACT_PATTERN.search(text) and len(text) < 300:
            warnings.append("contact_info_in_short_text")

        # ---- Homoglyph / evasion characters ----
        if _HOMOGLYPH_PATTERN.search(text):
            warnings.append("homoglyph_detected")

        # ---- Excessive emoji ----
        emoji_chars = sum(len(m) for m in _EMOJI_PATTERN.findall(text))
        if emoji_chars / max(len(text), 1) > 0.2:
            warnings.append("excessive_emoji")

        # ---- Consecutive same-character run ----
        max_run = 1
        cr = 1
        for i in range(1, len(text)):
            if text[i] == text[i - 1]:
                cr += 1
                max_run = max(max_run, cr)
            else:
                cr = 1
        if max_run > 8:
            warnings.append("long_consecutive_repeat")

        return warnings

    def _check_external_rules(self, text: str) -> tuple[list[str], list[str]]:
        """Check text against user-supplied external rules config.

        Returns (matched_category_names, actions_taken).
        """
        if not self._rules_loaded or not self._compiled_category_rules:
            return [], []

        global_settings = self._rules_config.get("global_settings", {})
        case_sensitive = global_settings.get("case_sensitive", False)
        search_text = text if case_sensitive else text.lower()

        matched_categories: list[str] = []
        actions: list[str] = []

        for cat_name, rules in self._compiled_category_rules.items():
            matched = False

            # Check terms (substring match)
            for term in rules["terms"]:
                if term and term in search_text:
                    matched = True
                    break

            # Check regex patterns
            if not matched:
                for compiled in rules["patterns"]:
                    if compiled.search(text):
                        matched = True
                        break

            if matched:
                matched_categories.append(cat_name)
                actions.append(rules["action"])

        return matched_categories, actions

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, text: str) -> EngineResult:
        """
        Predict whether text is risky (three-layer detection).

        Returns EngineResult with decision, score, matches, and categories.
        """
        # Guard: empty / too short
        if not text or len(text.strip()) < 3:
            return EngineResult(
                decision="approved",
                score=0.0,
                matches=[],
                reason="text_too_short",
                categories=[],
            )

        # ============================================================
        # Layer 1: External rules config (fast path — keyword match)
        # ============================================================
        ext_categories, ext_actions = self._check_external_rules(text)

        if ext_categories and "reject" in ext_actions:
            # Immediate reject on keyword match
            return EngineResult(
                decision="rejected",
                score=1.0,
                matches=[f"external_rule:{c}" for c in ext_categories],
                reason=f"matched {len(ext_categories)} external rule categories",
                categories=ext_categories,
            )

        # ============================================================
        # Layer 2: Built-in statistical rule checks
        # ============================================================
        rule_warnings = self._rule_based_check(text)
        stat_features = self._extract_features(text)
        stat_warnings: list[str] = []

        if stat_features.get("entropy", 0) < 2.5 and len(text) > 20:
            stat_warnings.append("low_entropy")
        if stat_features.get("special_char_ratio", 0) > 0.15:
            stat_warnings.append("high_special_chars")
        if stat_features.get("digit_ratio", 0) > 0.4:
            stat_warnings.append("high_digit_ratio")
        if stat_features.get("emoji_ratio", 0) > 0.2:
            stat_warnings.append("high_emoji_density")
        if stat_features.get("contact_info_flag", 0) == 1:
            stat_warnings.append("contact_info_detected")
        if stat_features.get("homoglyph_flag", 0) == 1:
            stat_warnings.append("homoglyph_evasion")
        if stat_features.get("consecutive_repeat_max", 0) > 10:
            stat_warnings.append("very_long_repeat_run")
        if stat_features.get("exclamation_ratio", 0) > 0.3:
            stat_warnings.append("high_exclamation_density")

        all_warnings = rule_warnings + stat_warnings
        cat_hints = [f"ext:{c}" for c in ext_categories]

        # ============================================================
        # Layer 3: ML model prediction
        # ============================================================
        ml_score = 0.5  # neutral default
        if self._loaded and self._model_bundle is not None:
            try:
                vectorizer = self._model_bundle["vectorizer"]
                scaler = self._model_bundle["scaler"]
                classifier = self._model_bundle["classifier"]

                text_tfidf = vectorizer.transform([text])

                # Feature order must match training
                feat = [
                    stat_features.get("entropy", 0),
                    stat_features.get("punctuation_ratio", 0),
                    stat_features.get("digit_ratio", 0),
                    stat_features.get("special_char_ratio", 0),
                    stat_features.get("repeated_char_ratio", 0),
                    stat_features.get("url_flag", 0),
                    # v2 extra features — model trained with these will use them
                    stat_features.get("contact_info_flag", 0),
                    stat_features.get("emoji_ratio", 0),
                    stat_features.get("exclamation_ratio", 0),
                    stat_features.get("consecutive_repeat_max", 0),
                    stat_features.get("homoglyph_flag", 0),
                ]
                from scipy.sparse import hstack as sparse_hstack
                combined = sparse_hstack([text_tfidf, np.array([feat])])

                # Handle dimension mismatch (v1 model has 6 features, v2 has 11)
                if combined.shape[1] != scaler.n_features_in_:
                    logger.debug(
                        f"Feature dimension mismatch: model expects "
                        f"{scaler.n_features_in_}, got {combined.shape[1]}. "
                        f"Truncating extra features."
                    )
                    combined = combined[:, : scaler.n_features_in_]

                scaled = scaler.transform(combined)

                proba = classifier.predict_proba(scaled)[0]
                if len(proba) > 1:
                    ml_score = float(proba[1])
            except Exception as exc:
                logger.warning(f"ML prediction failed: {exc} — using rule-based fallback")
                ml_score = 0.5

        # ============================================================
        # Combine scores
        # ============================================================
        warning_bonus = min(len(all_warnings) * 0.10, 0.40)
        ext_bonus = 0.30 if len(ext_actions) >= 2 else (0.15 if ext_actions else 0)
        final_score = min(ml_score + warning_bonus + ext_bonus, 1.0)

        # Decision
        if final_score >= self.HIGH_RISK_THRESHOLD or len(all_warnings) >= 4:
            decision = "rejected"
        elif final_score >= self.LOW_RISK_THRESHOLD or len(all_warnings) >= 2 or ext_actions:
            decision = "flagged"
        else:
            decision = "approved"

        reason_parts = []
        if self._loaded:
            reason_parts.append("ml_prediction")
        else:
            reason_parts.append("rule_based_fallback")
        if ext_categories:
            reason_parts.append(f"{len(ext_categories)}_ext_rules")
        if all_warnings:
            reason_parts.append(f"{len(all_warnings)}_warnings")

        return EngineResult(
            decision=decision,
            score=round(final_score, 4),
            matches=all_warnings + cat_hints,
            reason="+".join(reason_parts),
            categories=ext_categories,
        )

    # ------------------------------------------------------------------
    # Batch prediction
    # ------------------------------------------------------------------

    def predict_batch(self, texts: list[str]) -> list[EngineResult]:
        """Predict multiple texts at once."""
        return [self.predict(t) for t in texts]

"""
Code security detection engine.

Combines:
  - Regex pattern matching against known dangerous code patterns
  - ML classifier for detecting suspicious code snippets

Patterns cover: command injection, path traversal, destructive ops,
code injection, data exfiltration, resource abuse.
"""

import logging
import os
import re
from typing import Any

import joblib
import numpy as np

logger = logging.getLogger(__name__)


class EngineResult:
    """Result from a single engine's prediction."""

    __slots__ = ("decision", "score", "matches", "reason")

    def __init__(
        self,
        decision: str,
        score: float,
        matches: list[str],
        reason: str,
    ):
        self.decision = decision
        self.score = score
        self.matches = matches
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "score": self.score,
            "matches": self.matches,
            "reason": self.reason,
        }


# Built-in regex patterns (duplicated from dataset for engine independence)
DEFAULT_PATTERNS: dict[str, list[str]] = {
    "command_injection": [
        r"\bsystem\s*\(",
        r"\bsubprocess\s*\.",
        r"\bexec\s*\(",
        r"\beval\s*\(",
        r"os\.popen",
        r"shell\s*=\s*True",
        r"commands\.getoutput",
    ],
    "path_traversal": [
        r"\.\.\/\.\.\/",
        r"\.\.\\\.\.\\",
        r"/etc/passwd",
        r"/etc/shadow",
        r"\.ssh/id_rsa",
        r"\.aws/credentials",
    ],
    "destructive_ops": [
        r"\brm\s+-rf\b",
        r"\bdd\s+if=",
        r"mkfs\.",
        r":\(\)\s*\{\s*:\|:&\s*\};:",
        r"chmod\s+777",
        r">\s*/dev/sda",
    ],
    "code_injection": [
        r"__import__\s*\(",
        r"pickle\.loads?",
        r"yaml\.load\s*\(",
        r"marshal\.loads?",
        r"compile\s*\(.+exec",
    ],
    "data_exfil": [
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r"nc\s+-e\s+/bin/",
        r"socket\.connect",
        r"requests\.post.*password",
        r"base64\.b64decode",
    ],
    "resource_abuse": [
        r"while\s*True\s*:.*fork",
        r"multiprocessing.*unlimited",
        r"open\s*\([^)]*,\s*['\"]w['\"]\s*\).*while",
        r"__import__.*while.*True",
    ],
}


class CodeSecurityEngine:
    """
    Code security detection engine.

    Two-tier detection:
    1. Regex pattern matching (fast, deterministic)
    2. ML classifier (statistical, for obfuscated/suspicious code)
    """

    # Score thresholds
    REJECT_THRESHOLD = 0.8    # High confidence dangerous
    FLAG_THRESHOLD = 0.4      # Medium confidence, worth flagging

    def __init__(self):
        self._model_bundle: dict | None = None
        self._loaded = False
        self._patterns: dict[str, list[str]] = DEFAULT_PATTERNS
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._version: str = "unknown"
        self._compile_patterns()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def patterns(self) -> dict[str, list[str]]:
        return self._patterns

    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance."""
        self._compiled_patterns = {}
        for category, patterns in self._patterns.items():
            compiled = []
            for p in patterns:
                compiled.append(re.compile(p, re.IGNORECASE | re.MULTILINE))
            self._compiled_patterns[category] = compiled

    def load_model(self, model_path: str) -> bool:
        """
        Load pre-trained ML model from .pkl file.

        Returns True if loaded successfully.
        """
        if not os.path.exists(model_path):
            logger.warning(f"Code security model not found: {model_path}")
            return False

        self._model_bundle = joblib.load(model_path)
        self._loaded = True

        # Use patterns from model if available, otherwise keep defaults
        if self._model_bundle and "patterns" in self._model_bundle:
            self._patterns = self._model_bundle["patterns"]
            self._compile_patterns()

        # Try to read version
        meta_path = model_path.replace(".pkl", "_metadata.json")
        if os.path.exists(meta_path):
            import json
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self._version = meta.get("version", "unknown")

        logger.info(f"CodeSecurityEngine loaded (v{self._version}, {len(self._patterns)} pattern categories)")
        return True

    def _rule_match(self, code: str) -> tuple[bool, list[str]]:
        """
        Run rule-based pattern matching.

        Returns (has_matches, list_of_matched_categories).
        """
        matched_categories: list[str] = []
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(code):
                    matched_categories.append(category)
                    break  # one match per category is enough
        return len(matched_categories) > 0, matched_categories

    def _simple_tokenize(self, text: str) -> str:
        """Simple whitespace + identifier tokenizer for code."""
        tokens = re.findall(r"[a-zA-Z_]\w*|[0-9]+|[^\s\w]", text)
        return " ".join(tokens)

    def predict(self, code: str) -> EngineResult:
        """
        Analyze code snippet for security risks.

        Args:
            code: Code snippet to analyze

        Returns:
            EngineResult with decision, score, and matched patterns
        """
        if not code or len(code.strip()) < 3:
            return EngineResult(
                decision="approved",
                score=0.0,
                matches=[],
                reason="code_too_short",
            )

        # Step 1: Rule-based matching
        has_rule_matches, matched_categories = self._rule_match(code)

        # Step 2: ML model prediction
        ml_score = 0.5
        if self._loaded and self._model_bundle is not None:
            vectorizer = self._model_bundle["vectorizer"]
            scaler = self._model_bundle["scaler"]
            classifier = self._model_bundle["classifier"]

            code_tfidf = vectorizer.transform([code])

            # Pattern features
            pattern_feats = np.zeros((1, len(self._patterns)), dtype=float)
            for i, category in enumerate(self._patterns):
                if category in matched_categories:
                    pattern_feats[0, i] = 1.0

            from scipy.sparse import hstack as sparse_hstack
            combined = sparse_hstack([code_tfidf, pattern_feats])
            scaled = scaler.transform(combined)

            proba = classifier.predict_proba(scaled)[0]
            if len(proba) > 1:
                ml_score = float(proba[1])

        # Combine rule matches with ML score
        rule_bonus = min(len(matched_categories) * 0.2, 0.6)
        final_score = min(ml_score + rule_bonus, 1.0)

        # Also check: if critical pattern categories are matched, escalate
        critical_categories = {"destructive_ops", "code_injection", "data_exfil"}
        has_critical = bool(set(matched_categories) & critical_categories)

        # Decide
        if has_critical or final_score >= self.REJECT_THRESHOLD:
            decision = "rejected"
        elif has_rule_matches or final_score >= self.FLAG_THRESHOLD:
            decision = "flagged"
        else:
            decision = "approved"

        reason_parts = []
        if matched_categories:
            reason_parts.append(f"rule_match:{','.join(matched_categories)}")
        if self._loaded:
            reason_parts.append("ml_assisted")
        else:
            reason_parts.append("rule_only")

        return EngineResult(
            decision=decision,
            score=round(final_score, 4),
            matches=matched_categories,
            reason="; ".join(reason_parts),
        )

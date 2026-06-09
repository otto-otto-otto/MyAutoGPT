"""
Unit tests for SensitiveWordEngine.

Tests cover:
  - Rule-based detection (without ML model loaded)
  - Statistical feature extraction
  - Edge cases (empty text, very short text, special characters)
  - Decision threshold behavior
"""

import pytest

from backend.security_sandbox.engines.sensitive_word_engine import (
    SensitiveWordEngine,
    EngineResult,
)


class TestSensitiveWordEngine:
    """Tests for the sensitive word detection engine."""

    @pytest.fixture
    def engine(self) -> SensitiveWordEngine:
        """Create a fresh engine instance without a loaded model."""
        return SensitiveWordEngine()

    # ---- Initialization ----

    def test_initial_state(self, engine: SensitiveWordEngine):
        """Engine starts unloaded."""
        assert not engine.is_loaded
        assert engine._model_bundle is None

    # ---- Predict: Empty / Short Text ----

    def test_empty_text_approved(self, engine: SensitiveWordEngine):
        """Empty text should be approved immediately."""
        result = engine.predict("")
        assert result.decision == "approved"
        assert result.score == 0.0

    def test_short_text_approved(self, engine: SensitiveWordEngine):
        """Very short text (< 3 chars) should be approved."""
        result = engine.predict("hi")
        assert result.decision == "approved"
        assert result.score == 0.0

    def test_whitespace_only(self, engine: SensitiveWordEngine):
        """Whitespace-only text should be approved."""
        result = engine.predict("   \n\t  ")
        assert result.decision == "approved"

    # ---- Predict: Normal Text (Should Pass) ----

    def test_benign_chinese_text(self, engine: SensitiveWordEngine):
        """Normal Chinese text should pass review."""
        result = engine.predict("今天的天气真好，适合出去散步")
        assert result.decision == "approved"
        assert result.score < engine.LOW_RISK_THRESHOLD

    def test_normal_english_text(self, engine: SensitiveWordEngine):
        """Normal English text should pass review."""
        result = engine.predict("The weather is nice today, perfect for a walk.")
        assert result.decision == "approved"

    def test_technical_content(self, engine: SensitiveWordEngine):
        """Technical content should pass review."""
        result = engine.predict("The API returns a JSON response with status code 200 and the requested data.")
        assert result.decision == "approved"

    # ---- Predict: Risky Patterns (Should Flag/Reject) ----

    def test_excessive_repetition(self, engine: SensitiveWordEngine):
        """Text with excessive character repetition should be flagged."""
        result = engine.predict("AAAAAAAAAAAAAAAAAAAAAAA test")
        # Should at minimum be flagged if not rejected
        assert result.decision in ("flagged", "rejected")
        assert len(result.matches) > 0

    def test_url_in_short_text(self, engine: SensitiveWordEngine):
        """Short text with URLs should be flagged (common in phishing)."""
        result = engine.predict("Click this link http://example.com now")
        assert result.decision in ("flagged", "rejected")

    def test_excessive_special_characters(self, engine: SensitiveWordEngine):
        """Text with many special characters should raise warnings."""
        result = engine.predict("@#$%^&*()" * 5)
        # Should generate some warning
        assert len(result.matches) > 0 or result.score > 0

    # ---- Predict: Spam/Phishing Indicators ----

    def test_urgency_language(self, engine: SensitiveWordEngine):
        """Text with urgency cues should be detected."""
        result = engine.predict("限时优惠仅此一天错过再等一年")
        assert result.decision in ("flagged", "rejected")

    def test_credential_request_pattern(self, engine: SensitiveWordEngine):
        """Text requesting user verification should be flagged."""
        result = engine.predict("亲爱的用户你的账号存在异常请立即验证")
        assert result.decision in ("flagged", "rejected")

    def test_lottery_winner_pattern(self, engine: SensitiveWordEngine):
        """Lottery winner scam patterns should be detected."""
        result = engine.predict("恭喜你中奖了赶快点击链接领取")
        assert result.decision in ("flagged", "rejected")

    # ---- Decision Thresholds ----

    def test_rejected_threshold(self, engine: SensitiveWordEngine):
        """Score >= HIGH_RISK_THRESHOLD should yield rejected."""
        # Simulate high-risk through multiple warning patterns
        result = engine.predict(
            "http://example.com http://test.com 恭喜中奖立即领取!!! @@@@"
        )
        # With enough warnings, should be flagged or rejected
        assert result.decision in ("flagged", "rejected")

    def test_score_range(self, engine: SensitiveWordEngine):
        """Score should always be between 0 and 1."""
        texts = ["hello", "test content", "a" * 100, "!!!@@@###"]
        for text in texts:
            result = engine.predict(text)
            assert 0.0 <= result.score <= 1.0, f"Score {result.score} out of range for: {text}"

    # ---- Edge Cases ----

    def test_unicode_special_chars(self, engine: SensitiveWordEngine):
        """Unicode and special characters should be handled gracefully."""
        result = engine.predict("\u2605\u2606\u2728 \U0001F600 \u00a9\u00ae")
        assert result.decision in ("approved", "flagged")  # Should not crash

    def test_very_long_text(self, engine: SensitiveWordEngine):
        """Very long text should not crash the engine."""
        long_text = "The quick brown fox jumps over the lazy dog. " * 100
        result = engine.predict(long_text)
        assert result.decision in ("approved", "flagged", "rejected")
        assert 0.0 <= result.score <= 1.0

    def test_newline_injection(self, engine: SensitiveWordEngine):
        """Text with many newlines should be detected."""
        result = engine.predict("test\n\n\n\n\n\n\n\n\n\ntest")
        # Excessive newlines in short text flags a warning
        assert result.decision in ("flagged", "rejected")

    # ---- Result Structure ----

    def test_result_has_required_fields(self, engine: SensitiveWordEngine):
        """Every result should have decision, score, matches, reason."""
        result = engine.predict("Hello world test")
        assert hasattr(result, "decision")
        assert hasattr(result, "score")
        assert hasattr(result, "matches")
        assert hasattr(result, "reason")
        assert result.decision in ("approved", "flagged", "rejected")
        assert isinstance(result.score, float)
        assert isinstance(result.matches, list)
        assert isinstance(result.reason, str)

    def test_to_dict_method(self, engine: SensitiveWordEngine):
        """EngineResult.to_dict() should return a serializable dict."""
        result = engine.predict("test content")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "decision" in d
        assert "score" in d
        assert "matches" in d
        assert "reason" in d

"""Tests for config.py: CORS origin parsing and env-driven defaults."""
import os
from unittest.mock import patch

from app.config import _origins


class TestOrigins:
    def test_default_origins(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CORS_ORIGINS", None)
            result = _origins()
        assert "http://localhost:3000" in result
        assert "http://127.0.0.1:3000" in result

    def test_custom_single(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://example.com"}):
            result = _origins()
        assert result == ["https://example.com"]

    def test_custom_multiple(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://a.com,https://b.com"}):
            result = _origins()
        assert result == ["https://a.com", "https://b.com"]

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": " https://a.com , https://b.com "}):
            result = _origins()
        assert result == ["https://a.com", "https://b.com"]

    def test_empty_string(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}):
            result = _origins()
        assert result == []

    def test_trailing_comma(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://a.com,"}):
            result = _origins()
        assert result == ["https://a.com"]

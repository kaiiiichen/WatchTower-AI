"""Tests for gemini_status_browser (isolated adapter)."""
import json

from app.gemini_status_browser import (
    RPC_PATH_FRAGMENT,
    _parse_rpc_body,
    available,
    enabled,
)


class TestParseRpcBody:
    def test_json_array(self):
        raw = b'[{"1": "inc-1", "2": "Outage", "3": 1}]'
        out = _parse_rpc_body(raw, "application/json")
        assert isinstance(out, list)
        assert out[0]["2"] == "Outage"

    def test_json_with_xssi_prefix(self):
        raw = b")]}'\n" + json.dumps({"1": []}).encode()
        out = _parse_rpc_body(raw, "text/plain")
        assert out == {"1": []}

    def test_protobuf_bytes_fallback(self):
        raw = b"\x00\x00\x00\x00\x05\x0a\x03foo"
        out = _parse_rpc_body(raw, "application/octet-stream")
        assert out == raw


class TestFeatureFlags:
    def test_rpc_fragment(self):
        assert RPC_PATH_FRAGMENT == "ListIncidentsHistory"

    def test_enabled_respects_config(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "GEMINI_STATUS_BROWSER", True)
        assert enabled() is True
        monkeypatch.setattr(config, "GEMINI_STATUS_BROWSER", False)
        assert enabled() is False

    def test_available_when_disabled(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "GEMINI_STATUS_BROWSER", False)
        assert available() is False

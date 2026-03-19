"""Tests for hubui_brain.models — request parsing, response builders, capabilities."""

import json

from hubui_brain.models import (
    PROTOCOL_VERSION,
    Capabilities,
    ConversationTurn,
    QueryRequest,
    build_clarification_response,
    build_error_response,
    build_processing_response,
    build_success_response,
    build_tool_response,
)

# =============================================================================
# QueryRequest parsing
# =============================================================================

class TestQueryRequest:
    """Tests for QueryRequest.from_dict / from_json."""

    def test_from_dict_minimal(self, sample_query_data: dict):
        req = QueryRequest.from_dict(sample_query_data)
        assert req.session_id == "call-test-123"
        assert req.current_query == "What time do you open tomorrow?"
        assert req.caller_number == "+15551234567"
        assert req.business_number == "+15559876543"
        assert req.call_source == "sip"
        assert req.connection_type == "voice"
        assert req.total_turns == 0
        assert req.capabilities is None

    def test_from_dict_with_history(self, sample_query_with_history: dict):
        req = QueryRequest.from_dict(sample_query_with_history)
        assert len(req.conversation_history) == 2
        assert req.conversation_history[0].role == "user"
        assert req.conversation_history[0].content == "Hello"
        assert req.conversation_history[1].role == "assistant"
        assert req.total_turns == 2

    def test_from_dict_with_capabilities(self, sample_query_with_capabilities: dict):
        req = QueryRequest.from_dict(sample_query_with_capabilities)
        assert req.capabilities is not None
        assert len(req.capabilities.tools) == 3
        assert req.has_tool("_terminate_call") is True
        assert req.has_tool("_nonexistent") is False

    def test_from_dict_defaults(self):
        """Empty dict should produce safe defaults, not crash."""
        req = QueryRequest.from_dict({})
        assert req.session_id == ""
        assert req.current_query == ""
        assert req.call_source == "unknown"
        assert req.connection_type == "unknown"
        assert req.capabilities is None

    def test_from_json(self, sample_query_data: dict):
        json_str = json.dumps(sample_query_data)
        req = QueryRequest.from_json(json_str)
        assert req.session_id == "call-test-123"

    def test_roundtrip(self, sample_query_with_capabilities: dict):
        """from_dict → to_dict should preserve data."""
        req = QueryRequest.from_dict(sample_query_with_capabilities)
        d = req.to_dict()
        assert d["session_id"] == sample_query_with_capabilities["session_id"]
        assert d["current_query"] == sample_query_with_capabilities["current_query"]
        assert len(d["capabilities"]["tools"]) == 3

    def test_webrtc_fields(self, sample_webrtc_query: dict):
        req = QueryRequest.from_dict(sample_webrtc_query)
        assert req.call_source == "webrtc"
        assert req.user_email == "user@example.com"
        assert req.caller_number is None


# =============================================================================
# ConversationTurn
# =============================================================================

class TestConversationTurn:
    def test_from_dict(self):
        turn = ConversationTurn.from_dict(
            {"role": "user", "content": "Hi", "timestamp": "2026-01-01T00:00:00Z"}
        )
        assert turn.role == "user"
        assert turn.content == "Hi"
        assert turn.timestamp == "2026-01-01T00:00:00Z"

    def test_to_dict_without_timestamp(self):
        turn = ConversationTurn(role="assistant", content="Hello!")
        d = turn.to_dict()
        assert d == {"role": "assistant", "content": "Hello!"}


# =============================================================================
# Capabilities
# =============================================================================

class TestCapabilities:
    def test_from_dict(self, sample_query_with_capabilities: dict):
        caps = Capabilities.from_dict(sample_query_with_capabilities["capabilities"])
        assert caps.agent.type == "conversational"
        assert "_terminate_call" in [t.name for t in caps.tools]
        assert caps.has_tool("_terminate_call") is True
        assert caps.has_tool("_nonexistent") is False

    def test_roundtrip(self, sample_query_with_capabilities: dict):
        caps = Capabilities.from_dict(sample_query_with_capabilities["capabilities"])
        d = caps.to_dict()
        assert d["protocol_version"] == PROTOCOL_VERSION
        assert len(d["tools"]) == 3


# =============================================================================
# Response builders
# =============================================================================

class TestResponseBuilders:
    def test_processing_response(self):
        r = build_processing_response(message="Working...")
        assert r["status"] == "processing"
        assert r["message"] == "Working..."
        assert "play_hold_music" not in r

    def test_processing_with_hold_music(self):
        r = build_processing_response(message="Please hold.", play_hold_music=True)
        assert r["play_hold_music"] is True

    def test_processing_no_message(self):
        r = build_processing_response()
        assert r["status"] == "processing"
        assert "message" not in r

    def test_success_response(self):
        r = build_success_response(message="Done!")
        assert r["status"] == "success"
        assert r["message"] == "Done!"
        assert "data" not in r
        assert "tool" not in r

    def test_success_with_data(self):
        r = build_success_response(message="Ok", data={"key": "value"})
        assert r["data"] == {"key": "value"}

    def test_success_with_tool(self):
        r = build_success_response(message="Bye", tool="_terminate_call")
        assert r["tool"] == "_terminate_call"

    def test_clarification_response(self):
        r = build_clarification_response(message="Morning or afternoon?")
        assert r["status"] == "needs_clarification"
        assert r["message"] == "Morning or afternoon?"

    def test_error_response_minimal(self):
        r = build_error_response(message="Something failed.")
        assert r["status"] == "error"
        assert r["message"] == "Something failed."
        assert "error_code" not in r

    def test_error_response_full(self):
        r = build_error_response(
            message="Failed",
            error_code="TIMEOUT",
            error_details="30s timeout",
        )
        assert r["error_code"] == "TIMEOUT"
        assert r["error_details"] == "30s timeout"

    def test_tool_response(self):
        r = build_tool_response(tool="_terminate_call", message="Goodbye!")
        assert r["status"] == "success"
        assert r["tool"] == "_terminate_call"
        assert r["message"] == "Goodbye!"

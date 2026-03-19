"""Shared test fixtures for hubui-brain tests."""

import pytest

from hubui_brain.models import (
    QueryRequest,
)


@pytest.fixture
def sample_query_data() -> dict:
    """Minimal valid query payload."""
    return {
        "type": "query",
        "session_id": "call-test-123",
        "current_query": "What time do you open tomorrow?",
        "conversation_history": [],
        "caller_number": "+15551234567",
        "business_number": "+15559876543",
        "call_source": "sip",
        "connection_type": "voice",
        "timestamp": "2026-03-01T10:30:00Z",
        "total_turns": 0,
    }


@pytest.fixture
def sample_query_with_history(sample_query_data: dict) -> dict:
    """Query payload with conversation history."""
    data = sample_query_data.copy()
    data["conversation_history"] = [
        {"role": "user", "content": "Hello", "timestamp": "2026-03-01T10:29:00Z"},
        {"role": "assistant", "content": "Hi there!", "timestamp": "2026-03-01T10:29:01Z"},
    ]
    data["total_turns"] = 2
    data["current_query"] = "What time do you open tomorrow?"
    return data


@pytest.fixture
def sample_query_with_capabilities(sample_query_data: dict) -> dict:
    """Query payload with capabilities advertised."""
    data = sample_query_data.copy()
    data["capabilities"] = {
        "agent": {
            "type": "conversational",
            "modality": ["voice", "text"],
            "version": "1.0.0",
        },
        "tools": [
            {"name": "_heartbeat", "description": "Send a heartbeat"},
            {"name": "_heartbeat_music", "description": "Play hold music"},
            {"name": "_terminate_call", "description": "End the call"},
        ],
        "protocol_version": "1.0.0",
    }
    return data


@pytest.fixture
def sample_webrtc_query(sample_query_data: dict) -> dict:
    """Query payload from a WebRTC (web) call."""
    data = sample_query_data.copy()
    data["call_source"] = "webrtc"
    data["connection_type"] = "text"
    data["caller_number"] = None
    data["business_number"] = None
    data["user_email"] = "user@example.com"
    return data


@pytest.fixture
def query_request(sample_query_data: dict) -> QueryRequest:
    """Parsed QueryRequest object."""
    return QueryRequest.from_dict(sample_query_data)


@pytest.fixture
def query_request_with_capabilities(sample_query_with_capabilities: dict) -> QueryRequest:
    """Parsed QueryRequest with capabilities."""
    return QueryRequest.from_dict(sample_query_with_capabilities)

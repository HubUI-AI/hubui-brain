"""Tests for hubui_brain.context — QueryContext response methods & auto_process."""

import json
from unittest.mock import AsyncMock

import pytest

from hubui_brain.context import QueryContext
from hubui_brain.models import BRAIN_KEY_HEADER, QueryRequest

# =============================================================================
# Helpers
# =============================================================================

def _make_ctx(
    query_data: dict,
    api_key: str = "br_test_key",
    heartbeat_after: float | None = None,
    hold_music_after: float | None = None,
) -> tuple[QueryContext, AsyncMock]:
    """Create a QueryContext with a mocked websocket."""
    request = QueryRequest.from_dict(query_data)
    ws = AsyncMock()
    ws.send = AsyncMock()
    ctx = QueryContext(
        request=request,
        websocket=ws,
        api_key=api_key,
        heartbeat_after=heartbeat_after,
        hold_music_after=hold_music_after,
    )
    return ctx, ws


def _last_sent(ws: AsyncMock) -> dict:
    """Parse the last JSON message sent on the websocket."""
    call_args = ws.send.call_args_list[-1]
    return json.loads(call_args[0][0])


def _all_sent(ws: AsyncMock) -> list[dict]:
    """Parse all JSON messages sent on the websocket."""
    return [json.loads(c[0][0]) for c in ws.send.call_args_list]


# =============================================================================
# Properties
# =============================================================================

class TestQueryContextProperties:
    def test_basic_properties(self, sample_query_data: dict):
        ctx, _ = _make_ctx(sample_query_data)
        assert ctx.query == "What time do you open tomorrow?"
        assert ctx.session_id == "call-test-123"
        assert ctx.caller_number == "+15551234567"
        assert ctx.business_number == "+15559876543"
        assert ctx.call_source == "sip"
        assert ctx.connection_type == "voice"
        assert ctx.is_complete is False

    def test_capabilities_properties(self, sample_query_with_capabilities: dict):
        ctx, _ = _make_ctx(sample_query_with_capabilities)
        assert ctx.capabilities is not None
        assert len(ctx.available_tools) == 3
        assert ctx.has_tool("_terminate_call") is True
        assert ctx.has_tool("_nonexistent") is False

    def test_no_capabilities(self, sample_query_data: dict):
        ctx, _ = _make_ctx(sample_query_data)
        assert ctx.capabilities is None
        assert ctx.available_tools == []
        assert ctx.has_tool("_terminate_call") is False

    def test_webrtc_properties(self, sample_webrtc_query: dict):
        ctx, _ = _make_ctx(sample_webrtc_query)
        assert ctx.user_email == "user@example.com"
        assert ctx.call_source == "webrtc"


# =============================================================================
# Response methods
# =============================================================================

class TestResponseMethods:
    @pytest.mark.asyncio
    async def test_reply(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.reply("We open at 9 AM.")
        msg = _last_sent(ws)
        assert msg["status"] == "success"
        assert msg["message"] == "We open at 9 AM."
        assert msg[BRAIN_KEY_HEADER] == "br_test_key"
        assert ctx.is_complete is True

    @pytest.mark.asyncio
    async def test_reply_with_data(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.reply("Found it.", data={"id": 42})
        msg = _last_sent(ws)
        assert msg["data"] == {"id": 42}

    @pytest.mark.asyncio
    async def test_double_reply_raises(self, sample_query_data: dict):
        ctx, _ = _make_ctx(sample_query_data)
        await ctx.reply("First")
        with pytest.raises(RuntimeError, match="Final response already sent"):
            await ctx.reply("Second")

    @pytest.mark.asyncio
    async def test_ask_clarification(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.ask_clarification("Morning or afternoon?")
        msg = _last_sent(ws)
        assert msg["status"] == "needs_clarification"
        assert ctx.is_complete is True

    @pytest.mark.asyncio
    async def test_reply_error(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.reply_error("Oops", error_code="E1", error_details="detail")
        msg = _last_sent(ws)
        assert msg["status"] == "error"
        assert msg["error_code"] == "E1"
        assert ctx.is_complete is True

    @pytest.mark.asyncio
    async def test_say_processing(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.say_processing("Checking...")
        msg = _last_sent(ws)
        assert msg["status"] == "processing"
        assert msg["message"] == "Checking..."
        assert ctx.is_complete is False  # Non-final

    @pytest.mark.asyncio
    async def test_play_hold_music(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data)
        await ctx.play_hold_music("Please hold.")
        msg = _last_sent(ws)
        assert msg["status"] == "processing"
        assert msg["play_hold_music"] is True
        assert ctx.is_complete is False

    @pytest.mark.asyncio
    async def test_processing_after_final_raises(self, sample_query_data: dict):
        ctx, _ = _make_ctx(sample_query_data)
        await ctx.reply("done")
        with pytest.raises(RuntimeError):
            await ctx.say_processing("too late")

    @pytest.mark.asyncio
    async def test_terminate_call(self, sample_query_with_capabilities: dict):
        ctx, ws = _make_ctx(sample_query_with_capabilities)
        await ctx.terminate_call("Goodbye!")
        msg = _last_sent(ws)
        assert msg["status"] == "success"
        assert msg["tool"] == "_terminate_call"
        assert ctx.is_complete is True


# =============================================================================
# API key inclusion
# =============================================================================

class TestApiKeyInclusion:
    @pytest.mark.asyncio
    async def test_api_key_in_every_response(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data, api_key="br_secret")
        await ctx.say_processing("working")
        assert _all_sent(ws)[0][BRAIN_KEY_HEADER] == "br_secret"

    @pytest.mark.asyncio
    async def test_no_api_key_when_none(self, sample_query_data: dict):
        ctx, ws = _make_ctx(sample_query_data, api_key=None)
        await ctx.say_processing("working")
        assert BRAIN_KEY_HEADER not in _all_sent(ws)[0]


# =============================================================================
# auto_process
# =============================================================================

class TestAutoProcess:
    @pytest.mark.asyncio
    async def test_no_timing_passthrough(self, sample_query_data: dict):
        """When no timing is configured, auto_process just runs the coroutine."""
        ctx, _ = _make_ctx(sample_query_data)

        async def fast():
            return "result"

        result = await ctx.auto_process(fast())
        assert result == "result"

    @pytest.mark.asyncio
    async def test_fast_coroutine_no_heartbeat(self, sample_query_data: dict):
        """A coroutine that finishes quickly should NOT trigger heartbeat."""
        ctx, ws = _make_ctx(sample_query_data, heartbeat_after=5.0)

        async def fast():
            return "quick"

        result = await ctx.auto_process(fast())
        assert result == "quick"
        # No processing messages should have been sent
        assert ws.send.call_count == 0

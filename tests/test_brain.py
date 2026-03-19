"""Tests for hubui_brain.brain — Brain class, decorator, configuration."""

import os
import warnings
from unittest.mock import patch

from hubui_brain import Brain, QueryContext, __version__


class TestBrainInit:
    def test_defaults(self):
        brain = Brain(api_key="br_test")
        assert brain.api_key == "br_test"
        assert brain.debug is False
        assert brain.heartbeat_after is None
        assert brain.hold_music_after is None
        assert brain.shutdown_timeout == 5.0

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"HUBUI_BRAIN_API_KEY": "br_env_key"}):
            brain = Brain()
            assert brain.api_key == "br_env_key"

    def test_api_key_param_overrides_env(self):
        with patch.dict(os.environ, {"HUBUI_BRAIN_API_KEY": "br_env"}):
            brain = Brain(api_key="br_param")
            assert brain.api_key == "br_param"

    def test_no_api_key_warns(self):
        with patch.dict(os.environ, {}, clear=True):
            # Make sure HUBUI_BRAIN_API_KEY is not set
            os.environ.pop("HUBUI_BRAIN_API_KEY", None)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                Brain()
                assert len(w) == 1
                assert "No Brain API key" in str(w[0].message)

    def test_heartbeat_config(self):
        brain = Brain(
            api_key="br_test",
            heartbeat_after=3.0,
            hold_music_after=10.0,
            heartbeat_message="Working...",
            hold_music_message="Please hold.",
        )
        assert brain.heartbeat_after == 3.0
        assert brain.hold_music_after == 10.0
        assert brain.heartbeat_message == "Working..."
        assert brain.hold_music_message == "Please hold."


class TestOnQueryDecorator:
    def test_registers_handler(self):
        brain = Brain(api_key="br_test")

        @brain.on_query()
        async def handler(ctx: QueryContext):
            pass

        assert brain._handler is handler

    def test_decorator_returns_original_function(self):
        brain = Brain(api_key="br_test")

        @brain.on_query()
        async def handler(ctx: QueryContext):
            pass

        # The decorator should return the same function
        assert handler.__name__ == "handler"


class TestVersion:
    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_version_format(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestExports:
    def test_brain_importable(self):
        from hubui_brain import Brain
        assert Brain is not None

    def test_query_context_importable(self):
        from hubui_brain import QueryContext
        assert QueryContext is not None

    def test_query_request_importable(self):
        from hubui_brain import QueryRequest
        assert QueryRequest is not None

    def test_conversation_turn_importable(self):
        from hubui_brain import ConversationTurn
        assert ConversationTurn is not None

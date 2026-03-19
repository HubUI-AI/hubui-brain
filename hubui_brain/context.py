"""
Query context for HubUI Brain.

Provides a clean interface for responding to queries from the Voice Agent.
Hides WebSocket details and provides Pythonic methods for sending responses.

Protocol Version: 1.0.0
"""

import asyncio
import json
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Dict,
    List,
    Optional,
    TypeVar,
)

from hubui_brain.debug import get_debugger
from hubui_brain.models import (
    BRAIN_KEY_HEADER,
    Capabilities,
    ConversationTurn,
    QueryRequest,
    ToolDefinition,
    build_clarification_response,
    build_error_response,
    build_processing_response,
    build_success_response,
    build_tool_response,
)

if TYPE_CHECKING:
    from websockets.legacy.server import WebSocketServerProtocol

logger = logging.getLogger("hubui_brain")

# Known tools (Protocol v1.0.0)
TOOL_HEARTBEAT = "_heartbeat"
TOOL_HEARTBEAT_MUSIC = "_heartbeat_music"
TOOL_TERMINATE_CALL = "_terminate_call"

# Type for the result of auto_process
T = TypeVar('T')


class QueryContext:
    """
    Context object passed to query handlers.

    Provides access to the query data and methods for responding
    to the Voice Agent. All response methods are async.

    Attributes:
        request: The full QueryRequest object
        session_id: Unique session identifier
        query: The current user query (shorthand for request.current_query)
        history: Conversation history (shorthand for request.conversation_history)
        caller_number: Phone number of the caller
        business_number: Business phone number

    Example (Manual Heartbeats):
        @brain.on_query()
        async def handle(ctx: QueryContext):
            await ctx.say_processing("Looking that up...")
            result = await my_llm.generate(ctx.query)
            await ctx.reply(result)

    Example (Auto Heartbeats with auto_process):
        @brain.on_query()
        async def handle(ctx: QueryContext):
            # auto_process() monitors timing and sends heartbeats if configured!
            result = await ctx.auto_process(my_llm.generate(ctx.query))
            await ctx.reply(result)
    """

    def __init__(
        self,
        request: QueryRequest,
        websocket: "WebSocketServerProtocol",
        api_key: Optional[str] = None,
        # Auto-heartbeat configuration (used by auto_process)
        heartbeat_after: Optional[float] = None,
        hold_music_after: Optional[float] = None,
        heartbeat_message: Optional[str] = None,
        hold_music_message: Optional[str] = None
    ):
        """
        Initialize the context.

        Args:
            request: The parsed query request
            websocket: WebSocket connection (internal use)
            api_key: Brain API key for authentication (internal use)
            heartbeat_after: Seconds before auto heartbeat in auto_process (None = disabled)
            hold_music_after: Seconds before auto hold music in auto_process (None = disabled)
            heartbeat_message: Message for auto heartbeat (None = use default)
            hold_music_message: Message for auto hold music (None = use default)
        """
        self.request = request
        self._websocket = websocket
        self._api_key = api_key
        self._final_response_sent = False

        # Auto-heartbeat configuration (used by auto_process)
        self._heartbeat_after = heartbeat_after
        self._hold_music_after = hold_music_after
        self._heartbeat_message = heartbeat_message
        self._hold_music_message = hold_music_message

        # Tracking for auto_process
        self._heartbeat_sent = False
        self._hold_music_sent = False

    # =========================================================================
    # CONVENIENCE PROPERTIES
    # =========================================================================

    @property
    def session_id(self) -> str:
        """Unique session identifier."""
        return self.request.session_id

    @property
    def query(self) -> str:
        """The current user query."""
        return self.request.current_query

    @property
    def history(self) -> List[ConversationTurn]:
        """Conversation history (list of ConversationTurn)."""
        return self.request.conversation_history

    @property
    def caller_number(self) -> Optional[str]:
        """Phone number of the caller (E.164 format)."""
        return self.request.caller_number

    @property
    def business_number(self) -> Optional[str]:
        """Business phone number that received the call."""
        return self.request.business_number

    @property
    def user_email(self) -> Optional[str]:
        """Email of the user (WebRTC calls only)."""
        return self.request.user_email

    @property
    def total_turns(self) -> int:
        """Number of conversation turns."""
        return self.request.total_turns

    # =========================================================================
    # CAPABILITIES PROPERTIES (Protocol v1.0.0)
    # =========================================================================

    @property
    def capabilities(self) -> Optional[Capabilities]:
        """Voice Agent capabilities advertised in the request."""
        return self.request.capabilities

    @property
    def call_source(self) -> str:
        """Source of the call ("sip", "webrtc", or "unknown")."""
        return self.request.call_source

    @property
    def connection_type(self) -> str:
        """Interaction modality: \"voice\", \"text\", or \"unknown\"."""
        return self.request.connection_type

    @property
    def available_tools(self) -> List[ToolDefinition]:
        """List of tools the Voice Agent can execute."""
        if not self.request.capabilities:
            return []
        return self.request.capabilities.tools

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is available.

        Args:
            name: Tool name (e.g., "_terminate_call")

        Returns:
            True if the tool is available, False otherwise

        Example:
            if ctx.has_tool("_terminate_call"):
                await ctx.terminate_call("Goodbye!")
        """
        return self.request.has_tool(name)

    # =========================================================================
    # RESPONSE METHODS
    # =========================================================================

    async def _send(self, data: Dict[str, Any]) -> None:
        """
        Send a response to the Voice Agent.

        Automatically includes the Brain API key for authentication.

        Args:
            data: Response dictionary to send as JSON
        """
        # Include API key for Voice Agent validation
        if self._api_key:
            data[BRAIN_KEY_HEADER] = self._api_key

        debugger = get_debugger()
        debugger.log_outgoing(data, self.session_id)

        json_str = json.dumps(data, ensure_ascii=False, default=str)
        await self._websocket.send(json_str)

    async def say_processing(self, message: str) -> None:
        """
        Send a processing heartbeat with a message for the agent to speak.

        Use this to keep the user informed while doing long operations.
        Can be called multiple times.

        Args:
            message: Text for the Voice Agent to speak

        Example:
            await ctx.say_processing("Let me check our calendar...")
            # ... do work ...
            await ctx.say_processing("Almost done...")
        """
        if self._final_response_sent:
            raise RuntimeError("Cannot send processing after final response")

        response = build_processing_response(message=message, play_hold_music=False)
        await self._send(response)

    async def play_hold_music(self, message: Optional[str] = None) -> None:
        """
        Start playing hold music on the Voice Agent.

        Use this for operations that take 10+ seconds. The music loops
        until a final response is sent.

        Args:
            message: Optional message to speak before music starts

        Example:
            await ctx.play_hold_music("This might take a moment. Please hold.")
            # ... long operation ...
            await ctx.reply("Here's what I found...")
        """
        if self._final_response_sent:
            raise RuntimeError("Cannot send processing after final response")

        response = build_processing_response(message=message, play_hold_music=True)
        await self._send(response)

    async def reply(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a successful response to the Voice Agent.

        This is a final response - no more messages can be sent after this.
        The Voice Agent will speak the message to the user.

        Args:
            message: The response for the agent to speak (natural language)
            data: Optional structured data for logging/debugging

        Example:
            await ctx.reply(
                "I found 3 appointments available: 9 AM, 11 AM, and 2 PM.",
                data={"appointments": [...]}
            )
        """
        if self._final_response_sent:
            raise RuntimeError("Final response already sent")

        self._final_response_sent = True
        response = build_success_response(message=message, data=data)
        await self._send(response)

    async def ask_clarification(self, message: str) -> None:
        """
        Ask the user for more information.

        This is a final response - the Voice Agent will ask the user
        the clarification question, and a new query will come with
        their answer.

        Args:
            message: The clarification question to ask

        Example:
            await ctx.ask_clarification(
                "I can help schedule an appointment. "
                "Are you looking for a morning or afternoon time?"
            )
        """
        if self._final_response_sent:
            raise RuntimeError("Final response already sent")

        self._final_response_sent = True
        response = build_clarification_response(message=message)
        await self._send(response)

    async def reply_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> None:
        """
        Send an error response to the Voice Agent.

        This is a final response. The message should be user-friendly
        as the agent will speak it to the user.

        Args:
            message: User-friendly error message for agent to speak
            error_code: Machine-readable error code (for logging)
            error_details: Technical details (for debugging)

        Example:
            await ctx.reply_error(
                "I'm sorry, I couldn't access our scheduling system. "
                "Please try again in a moment.",
                error_code="CALENDAR_UNAVAILABLE",
                error_details="Timeout connecting to calendar API"
            )
        """
        if self._final_response_sent:
            raise RuntimeError("Final response already sent")

        self._final_response_sent = True
        response = build_error_response(
            message=message,
            error_code=error_code,
            error_details=error_details
        )
        await self._send(response)

    # =========================================================================
    # TOOL METHODS (Protocol v1.0.0)
    # =========================================================================

    async def terminate_call(self, message: str) -> None:
        """
        End the call gracefully (SIP calls only).

        The Voice Agent will speak the message and then hang up.
        This is a final response - no more messages can be sent.

        Note: This tool is only available for SIP calls. Check with
        has_tool("_terminate_call") before calling.

        Args:
            message: Goodbye message for the agent to speak

        Example:
            if ctx.has_tool("_terminate_call"):
                await ctx.terminate_call("Thank you for calling. Goodbye!")
            else:
                await ctx.reply("Thank you for calling. Goodbye!")
        """
        if self._final_response_sent:
            raise RuntimeError("Final response already sent")

        self._final_response_sent = True
        response = build_tool_response(
            tool=TOOL_TERMINATE_CALL,
            message=message
        )
        await self._send(response)

    # =========================================================================
    # STATE CHECKING
    # =========================================================================

    @property
    def is_complete(self) -> bool:
        """Whether a final response has been sent."""
        return self._final_response_sent

    # =========================================================================
    # MANAGED MODE METHODS
    # =========================================================================

    async def auto_process(
        self,
        coroutine: Awaitable[T],
        heartbeat_after: Optional[float] = None,
        hold_music_after: Optional[float] = None,
        heartbeat_message: Optional[str] = None,
        hold_music_message: Optional[str] = None
    ) -> T:
        """
        Run an async operation with automatic heartbeat monitoring.

        If heartbeat_after/hold_music_after are configured (on Brain or passed here),
        SDK monitors how long the operation takes and automatically sends
        heartbeat/hold music messages to keep the user informed.

        If no timing is configured, this simply runs the coroutine.

        Args:
            coroutine: The async operation to run (e.g., LLM call)
            heartbeat_after: Seconds before heartbeat (overrides Brain default)
            hold_music_after: Seconds before hold music (overrides Brain default)
            heartbeat_message: Message for heartbeat (default: "One moment please...")
            hold_music_message: Message for hold music (default: "This is taking a bit longer. Please hold...")

        Returns:
            The result of the coroutine

        Example (no auto heartbeats - just wraps coroutine):
            brain = Brain()  # No timing configured
            result = await ctx.auto_process(my_llm(ctx.query))

        Example (auto heartbeats enabled):
            brain = Brain(heartbeat_after=3.0, hold_music_after=10.0)
            result = await ctx.auto_process(my_llm(ctx.query))
            # Sends heartbeat at 3s, hold music at 10s automatically

        Example (override timing per-call):
            result = await ctx.auto_process(
                my_llm(ctx.query),
                heartbeat_after=2.0,
                hold_music_after=8.0,
                heartbeat_message="Thinking hard..."
            )
        """
        # Determine effective timing (call override > Brain config > None)
        hb_after = heartbeat_after if heartbeat_after is not None else self._heartbeat_after
        hm_after = hold_music_after if hold_music_after is not None else self._hold_music_after

        # Default messages if timing is enabled but no message provided
        hb_msg = heartbeat_message or self._heartbeat_message or "One moment please..."
        hm_msg = hold_music_message or self._hold_music_message or "This is taking a bit longer. Please hold..."

        # If no timing configured at all, just run the coroutine directly
        if hb_after is None and hm_after is None:
            return await coroutine

        # Create the main task
        task = asyncio.ensure_future(coroutine)

        start_time = asyncio.get_event_loop().time()
        check_interval = 0.1  # Check every 100ms

        while not task.done():
            try:
                # Wait a bit, then check
                await asyncio.wait_for(asyncio.shield(task), timeout=check_interval)
                break  # Task completed
            except asyncio.TimeoutError:
                # Task still running, check elapsed time
                elapsed = asyncio.get_event_loop().time() - start_time

                # Send heartbeat if threshold reached and configured
                if hb_after is not None and elapsed >= hb_after and not self._heartbeat_sent and not self._final_response_sent:
                    logger.info(f"⏱️ Auto heartbeat at {elapsed:.1f}s: {hb_msg}")
                    await self.say_processing(hb_msg)
                    self._heartbeat_sent = True

                # Send hold music if threshold reached and configured
                if hm_after is not None and elapsed >= hm_after and not self._hold_music_sent and not self._final_response_sent:
                    logger.info(f"⏱️ Auto hold music at {elapsed:.1f}s: {hm_msg}")
                    await self.play_hold_music(hm_msg)
                    self._hold_music_sent = True

        # Return the result
        return await task

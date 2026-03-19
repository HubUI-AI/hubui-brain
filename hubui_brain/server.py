"""
WebSocket server for HubUI Brain.

Async WebSocket server that handles connections from Voice Agents.
Features:
- Multiple concurrent connections (one per call)
- Resilient error handling (log & continue)
- Graceful shutdown with configurable timeout
- API key authentication via handshake and in every response
- Protocol version negotiation (v1.0.0)

Authentication Flow:
1. Voice Agent connects to Brain backend
2. Brain immediately sends handshake message with API key and protocol version
3. Voice Agent validates key hash before accepting connection
4. Brain includes API key in every subsequent response
5. Voice Agent validates key on every message received

Protocol Version: 1.0.0
"""

import asyncio
import json
import signal
from typing import Any, Callable, Coroutine, Optional, Set

import websockets
from websockets.legacy.server import WebSocketServerProtocol, serve

from hubui_brain.context import QueryContext
from hubui_brain.debug import BrainDebugger, set_debugger
from hubui_brain.models import (
    BRAIN_KEY_HEADER,
    PROTOCOL_VERSION,
    QueryRequest,
    build_error_response,
)

# Type alias for query handler
QueryHandler = Callable[[QueryContext], Coroutine[Any, Any, None]]


class BrainServer:
    """
    Async WebSocket server for the Brain backend.

    Handles connections from Voice Agents and dispatches queries
    to registered handlers.

    Attributes:
        host: Server bind address
        port: Server port
        shutdown_timeout: Seconds to wait for active connections on shutdown
        api_key: Brain API key for authentication
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        debug: bool = False,
        shutdown_timeout: float = 5.0,
        api_key: Optional[str] = None,
        # Auto-heartbeat configuration (used by auto_process)
        heartbeat_after: Optional[float] = None,
        hold_music_after: Optional[float] = None,
        heartbeat_message: Optional[str] = None,
        hold_music_message: Optional[str] = None
    ):
        """
        Initialize the server.

        Args:
            host: Address to bind to (default: all interfaces)
            port: Port to listen on
            debug: Enable debug logging
            shutdown_timeout: Seconds to wait for connections on shutdown
            api_key: Brain API key for authentication with Voice Agent
            heartbeat_after: Seconds before auto heartbeat in auto_process (None = disabled)
            hold_music_after: Seconds before auto hold music in auto_process (None = disabled)
            heartbeat_message: Message for auto heartbeat (None = use default)
            hold_music_message: Message for auto hold music (None = use default)
        """
        self.host = host
        self.port = port
        self.shutdown_timeout = shutdown_timeout
        self.api_key = api_key

        # Auto-heartbeat configuration (used by auto_process)
        self._heartbeat_after = heartbeat_after
        self._hold_music_after = hold_music_after
        self._heartbeat_message = heartbeat_message
        self._hold_music_message = hold_music_message

        # Debug logging
        self._debugger = BrainDebugger(enabled=debug)
        set_debugger(self._debugger)

        # Handler registration
        self._query_handler: Optional[QueryHandler] = None

        # Connection tracking
        self._active_connections: Set[WebSocketServerProtocol] = set()
        self._server: Optional[Any] = None
        self._shutdown_event: Optional[asyncio.Event] = None

    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug logging."""
        self._debugger.enabled = enabled

    def set_query_handler(self, handler: QueryHandler) -> None:
        """
        Register the query handler.

        Args:
            handler: Async function that receives QueryContext
        """
        self._query_handler = handler

    async def _send_handshake(self, websocket: WebSocketServerProtocol) -> bool:
        """
        Send handshake message to Voice Agent immediately after connection.

        The handshake includes our API key so the Voice Agent can validate
        we are an authorized Brain backend before accepting any queries.

        Protocol v1.0.0: Handshake now includes protocol_version for
        version negotiation and compatibility checking.

        Args:
            websocket: The WebSocket connection

        Returns:
            True if handshake sent successfully, False otherwise
        """
        try:
            handshake = {
                "type": "handshake",
                "version": "1.0",
                "protocol_version": PROTOCOL_VERSION,  # Protocol v1.0.0
                "server": "hubui-brain"
            }

            # Include API key for Voice Agent validation
            if self.api_key:
                handshake[BRAIN_KEY_HEADER] = self.api_key

            self._debugger.log_server("Sending handshake to Voice Agent", "info")
            await websocket.send(json.dumps(handshake))
            self._debugger.log_server(f"Handshake sent (protocol v{PROTOCOL_VERSION})", "success")
            return True

        except Exception as e:
            self._debugger.log_server(f"Failed to send handshake: {e}", "error")
            return False

    async def _handle_connection(
        self,
        websocket: WebSocketServerProtocol
    ) -> None:
        """
        Handle a single WebSocket connection (one call session).

        Each connection can receive multiple queries during the call.
        """
        # Track connection
        self._active_connections.add(websocket)
        session_id = "unknown"

        try:
            self._debugger.log_connection(session_id, "connected")

            # Send handshake immediately after connection
            if not await self._send_handshake(websocket):
                self._debugger.log_server("Closing connection due to handshake failure", "error")
                return
            async for message in websocket:
                try:
                    # Parse incoming message
                    data = json.loads(message)
                    session_id = data.get("session_id", "unknown")

                    # Log incoming
                    self._debugger.log_incoming(data, session_id)

                    # Parse into request object
                    request = QueryRequest.from_dict(data)

                    # Create context with API key and auto-heartbeat configuration
                    ctx = QueryContext(
                        request=request,
                        websocket=websocket,
                        api_key=self.api_key,
                        heartbeat_after=self._heartbeat_after,
                        hold_music_after=self._hold_music_after,
                        heartbeat_message=self._heartbeat_message,
                        hold_music_message=self._hold_music_message
                    )

                    # Dispatch to handler
                    if self._query_handler:
                        try:
                            await self._query_handler(ctx)

                            # Ensure handler sent a final response
                            if not ctx.is_complete:
                                self._debugger.log_server(
                                    f"Handler did not send final response for session {session_id}",
                                    "warning"
                                )
                                await ctx.reply_error(
                                    "I encountered an issue processing your request. "
                                    "Please try again."
                                )
                        except Exception as handler_error:
                            # Handler raised an exception - send error response
                            self._debugger.log_server(
                                f"Handler error: {handler_error}",
                                "error"
                            )
                            if not ctx.is_complete:
                                await ctx.reply_error(
                                    "I'm sorry, something went wrong. Please try again.",
                                    error_code="HANDLER_ERROR",
                                    error_details=str(handler_error)
                                )
                    else:
                        # No handler registered
                        self._debugger.log_server("No query handler registered", "error")
                        response = build_error_response(
                            "I'm not configured to handle queries yet.",
                            error_code="NO_HANDLER"
                        )
                        # Include API key in error response
                        if self.api_key:
                            response[BRAIN_KEY_HEADER] = self.api_key
                        await websocket.send(json.dumps(response))

                except json.JSONDecodeError as e:
                    # Malformed JSON - log and send error response
                    self._debugger.log_server(f"Malformed JSON: {e}", "error")
                    response = build_error_response(
                        "I received a malformed request.",
                        error_code="MALFORMED_JSON",
                        error_details=str(e)
                    )
                    # Include API key in error response
                    if self.api_key:
                        response[BRAIN_KEY_HEADER] = self.api_key
                    await websocket.send(json.dumps(response))

                except Exception as e:
                    # Unexpected error - log and send error response
                    self._debugger.log_server(f"Unexpected error: {e}", "error")
                    response = build_error_response(
                        "An unexpected error occurred.",
                        error_code="INTERNAL_ERROR",
                        error_details=str(e)
                    )
                    # Include API key in error response
                    if self.api_key:
                        response[BRAIN_KEY_HEADER] = self.api_key
                    await websocket.send(json.dumps(response))

        except websockets.exceptions.ConnectionClosed as e:
            self._debugger.log_server(
                f"Connection closed: {e.code} {e.reason}",
                "info"
            )

        except Exception as e:
            self._debugger.log_server(f"Connection error: {e}", "error")

        finally:
            # Clean up connection tracking
            self._active_connections.discard(websocket)
            self._debugger.log_connection(session_id, "disconnected")

    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown with timeout."""
        self._debugger.log_server("Shutdown initiated...", "warning")

        # Stop accepting new connections
        if self._server:
            self._server.close()

        # Wait for active connections to finish
        if self._active_connections:
            self._debugger.log_server(
                f"Waiting for {len(self._active_connections)} active connection(s)...",
                "info"
            )

            # Give connections time to finish
            try:
                await asyncio.wait_for(
                    self._wait_for_connections(),
                    timeout=self.shutdown_timeout
                )
                self._debugger.log_server("All connections closed gracefully", "success")
            except asyncio.TimeoutError:
                self._debugger.log_server(
                    f"Timeout reached, closing {len(self._active_connections)} connection(s)",
                    "warning"
                )
                # Force close remaining connections
                for ws in list(self._active_connections):
                    await ws.close(1001, "Server shutting down")

        if self._shutdown_event:
            self._shutdown_event.set()

    async def _wait_for_connections(self) -> None:
        """Wait for all active connections to close."""
        while self._active_connections:
            await asyncio.sleep(0.1)

    def _setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Setup signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self._graceful_shutdown())
                )
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

    async def start(self) -> None:
        """
        Start the WebSocket server.

        This method runs until shutdown is triggered (SIGINT/SIGTERM).
        """
        self._shutdown_event = asyncio.Event()

        # Setup signal handlers
        loop = asyncio.get_running_loop()
        self._setup_signal_handlers(loop)

        # Start server
        self._debugger.log_server(
            f"🧠 Brain server starting on ws://{self.host}:{self.port}",
            "success"
        )

        async with serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=60,
        ) as server:
            self._server = server
            self._debugger.log_server(
                f"🧠 Brain server listening on ws://{self.host}:{self.port}",
                "success"
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        self._debugger.log_server("🧠 Brain server stopped", "info")

    def run(self) -> None:
        """
        Start the server (blocking).

        Convenience method that handles asyncio.run() for you.
        """
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            pass  # Clean exit on Ctrl+C

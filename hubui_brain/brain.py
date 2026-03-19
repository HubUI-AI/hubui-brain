"""
Main Brain class for HubUI Brain.

Provides the primary interface for building Voice Agent backends.
Uses decorators for clean handler registration.
"""

import os
from typing import Callable, Optional

from hubui_brain.server import BrainServer, QueryHandler


class Brain:
    """
    Main class for building Voice Agent backends.

    The Brain handles complex queries from Voice Agents, processes them
    using your LLM/logic, and sends responses back.

    Authentication:
        The HubUI Brain includes your API key in every response sent to the
        Voice Agent. The Voice Agent validates by hashing the key and
        comparing to a stored hash. This prevents unauthorized backends
        from impersonating your Brain.

        Set the API key via:
        - `api_key` parameter in constructor
        - `HUBUI_BRAIN_API_KEY` environment variable

    Example (Manual Heartbeats):
        brain = Brain(debug=True)

        @brain.on_query()
        async def handle_query(ctx: QueryContext):
            await ctx.say_processing("Let me check...")  # You control
            answer = await my_llm.generate(ctx.query)
            await ctx.reply(answer)

    Example (Auto Heartbeats with auto_process):
        brain = Brain(
            heartbeat_after=3.0,    # Auto heartbeat after 3 sec
            hold_music_after=10.0,  # Auto hold music after 10 sec
            debug=True
        )

        @brain.on_query()
        async def handle_query(ctx: QueryContext):
            # auto_process() monitors timing and sends heartbeats!
            answer = await ctx.auto_process(
                my_llm.generate(ctx.query)
            )
            await ctx.reply(answer)

    Attributes:
        heartbeat_after: Seconds before auto heartbeat in auto_process() (None = disabled)
        hold_music_after: Seconds before auto hold music in auto_process() (None = disabled)
        heartbeat_message: Message for auto heartbeat (None = use default)
        hold_music_message: Message for auto hold music (None = use default)
        debug: Whether debug logging is enabled
        shutdown_timeout: Seconds to wait for connections on shutdown
        api_key: Brain API key for authentication with Voice Agent
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        heartbeat_after: Optional[float] = None,
        hold_music_after: Optional[float] = None,
        heartbeat_message: Optional[str] = None,
        hold_music_message: Optional[str] = None,
        debug: bool = False,
        shutdown_timeout: float = 5.0
    ):
        """
        Initialize the Brain.

        Args:
            api_key: Brain API key for authentication. If not provided,
                    falls back to HUBUI_BRAIN_API_KEY environment variable.
            heartbeat_after: Seconds before auto heartbeat in auto_process() (None = disabled)
            hold_music_after: Seconds before auto hold music in auto_process() (None = disabled)
            heartbeat_message: Message to speak for auto heartbeat
            hold_music_message: Message to speak before hold music
            debug: Enable debug logging (shows all WebSocket messages)
            shutdown_timeout: Seconds to wait for active calls on shutdown
        """
        self.debug = debug
        self.shutdown_timeout = shutdown_timeout
        self._handler: Optional[QueryHandler] = None

        # Auto-heartbeat configuration (used by auto_process)
        self.heartbeat_after = heartbeat_after
        self.hold_music_after = hold_music_after
        self.heartbeat_message = heartbeat_message
        self.hold_music_message = hold_music_message

        # API key for authentication
        self.api_key = api_key or os.environ.get("HUBUI_BRAIN_API_KEY")
        if not self.api_key:
            import warnings
            warnings.warn(
                "No Brain API key provided. Set api_key parameter or "
                "HUBUI_BRAIN_API_KEY environment variable for production use."
            )

    def on_query(self) -> Callable[[QueryHandler], QueryHandler]:
        """
        Decorator to register a query handler.

        The handler receives a QueryContext with the query data and
        methods for responding.

        Example:
            @brain.on_query()
            async def handle(ctx: QueryContext):
                print(f"Query: {ctx.query}")
                await ctx.reply("Here's your answer!")

        Returns:
            Decorator function
        """
        def decorator(func: QueryHandler) -> QueryHandler:
            self._handler = func
            return func
        return decorator

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8080
    ) -> None:
        """
        Start the Brain server (blocking).

        This starts the WebSocket server and listens for connections
        from Voice Agents. The method blocks until shutdown.

        Args:
            host: Address to bind to (default: all interfaces)
            port: Port to listen on (default: 8080)

        Example:
            brain.run(host="0.0.0.0", port=8080)
        """
        server = BrainServer(
            host=host,
            port=port,
            debug=self.debug,
            shutdown_timeout=self.shutdown_timeout,
            api_key=self.api_key,
            heartbeat_after=self.heartbeat_after,
            hold_music_after=self.hold_music_after,
            heartbeat_message=self.heartbeat_message,
            hold_music_message=self.hold_music_message
        )

        if self._handler:
            server.set_query_handler(self._handler)

        server.run()

    async def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8080
    ) -> None:
        """
        Start the Brain server (async).

        Use this if you need to integrate with an existing asyncio loop.

        Args:
            host: Address to bind to
            port: Port to listen on

        Example:
            async def main():
                await brain.start(port=8080)

            asyncio.run(main())
        """
        server = BrainServer(
            host=host,
            port=port,
            debug=self.debug,
            shutdown_timeout=self.shutdown_timeout,
            api_key=self.api_key,
            heartbeat_after=self.heartbeat_after,
            hold_music_after=self.hold_music_after,
            heartbeat_message=self.heartbeat_message,
            hold_music_message=self.hold_music_message
        )

        if self._handler:
            server.set_query_handler(self._handler)

        await server.start()

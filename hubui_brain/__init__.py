"""
HubUI Brain - Python library for building Voice Agent backends.

This SDK provides a Pythonic interface for creating the "Brain" component
of a Compositional AI voice agent. The Brain handles complex queries that
require reasoning, tool calls, or access to external knowledge.

Quick Start (Manual Heartbeats):
    from hubui_brain import Brain, QueryContext

    brain = Brain(debug=True)

    @brain.on_query()
    async def handle_query(ctx: QueryContext):
        await ctx.say_processing("Let me check on that...")
        answer = await my_llm.generate(ctx.query)
        await ctx.reply(answer)

    brain.run(host="0.0.0.0", port=8080)

Quick Start (Auto Heartbeats with auto_process):
    from hubui_brain import Brain, QueryContext

    brain = Brain(
        heartbeat_after=3.0,    # Auto heartbeat after 3 sec (None = disabled)
        hold_music_after=10.0,  # Auto hold music after 10 sec (None = disabled)
        debug=True
    )

    @brain.on_query()
    async def handle_query(ctx: QueryContext):
        # auto_process monitors timing and sends heartbeats if configured!
        answer = await ctx.auto_process(my_llm.generate(ctx.query))
        await ctx.reply(answer)

    brain.run(host="0.0.0.0", port=8080)
"""

__version__ = "0.1.0"

from hubui_brain.brain import Brain
from hubui_brain.context import QueryContext
from hubui_brain.models import ConversationTurn, QueryRequest

__all__ = [
    "Brain",
    "QueryContext",
    "QueryRequest",
    "ConversationTurn",
    "__version__",
]

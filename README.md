# HubUI Brain

Python SDK for building the reasoning backend of a [HubUI](https://hubui.ai) voice AI — the **Brain**.

**SDK Version: 0.1.0.post1**

[Get Started Free](https://app.hubui.ai) · [Documentation](https://app.hubui.ai/documentation) · [Discord](https://discord.gg/9HZBN6ZeU6)

---

## Why HubUI Brain?

If you already have an AI agent that works — built with OpenAI, LangChain, LangGraph, or your own stack — HubUI lets you **plug it in and instantly give it a voice, a phone number, and a chat interface**. Voice and text chat in the browser, callable phone numbers — all from one SDK.

Most voice AI platforms freeze the conversation while your backend thinks. HubUI's Voice Agent keeps talking naturally — acknowledging the caller, providing status updates, even playing hold music — while your Brain processes in the background. **Zero dead air. Sub-500ms voice latency.**

Your existing reasoning code becomes the Brain. The SDK handles the WebSocket protocol. HubUI handles everything else — voice, phone, and text.

---

## Overview

```
┌─────────────────────┐         WebSocket         ┌─────────────────────┐
│   🎭 Voice Agent    │ ◄──────────────────────►  │   🧠 Your Brain     │
│   (HubUI Managed)   │                           │   (Your Backend)    │
│                     │                           │                     │
│  • Handles the call │                           │  • Reasons          │
│  • Engages the user │                           │  • Accesses data    │
│  • Executes actions │                           │  • Makes decisions  │
└─────────────────────┘                           └─────────────────────┘
```

HubUI's Voice Agent handles the real-time call experience. Your **Brain** handles the intelligence — it receives queries from the Voice Agent over a persistent WebSocket connection, runs your reasoning logic, and sends back responses.

The **HubUI Brain SDK** abstracts the entire WebSocket protocol so you can focus entirely on building your reasoning logic with any framework you choose.

---

## Installation

### Prerequisites

- Python 3.10+
- A HubUI Voice Agent configured to point to your Brain's URL
- A Brain API key (generated in the HubUI dashboard when you create a Brain)

### Install via pip (recommended)

```bash
pip install hubui-brain
```

### Install from source:

```bash
cd hubui-brain
pip install -e .
```

### Install from GitHub

```bash
pip install "git+https://github.com/HubUI-AI/hubui-brain.git"
```

---

## Quick Start

### Option 1 — Manual Heartbeats

You control exactly when to send follow-up status updates during longer operations.

```python
from hubui_brain import Brain, QueryContext

brain = Brain(api_key="br_xxx", debug=True)

@brain.on_query()
async def handle_query(ctx: QueryContext):
    # Your reasoning logic
    answer = await my_reasoning_engine.process(ctx.query)

    # Send the final response back
    await ctx.reply(answer)

brain.run(host="0.0.0.0", port=8080)
```

> **Note:** You don't need to send an initial acknowledgment like "Let me check on that" — HubUI's Voice Agent automatically speaks an instant acknowledgment to the caller before your Brain even receives the query. The caller is never left in silence.

### Option 2 — Auto Heartbeats with `auto_process()`

Configure timing thresholds on `Brain` and let the SDK send follow-up status updates automatically if your processing takes a while.

```python
from hubui_brain import Brain, QueryContext

brain = Brain(
    api_key="br_xxx",
    heartbeat_after=5.0,      # Send a follow-up status after 5 seconds
    hold_music_after=15.0,    # Start hold music after 15 seconds
    debug=True
)

@brain.on_query()
async def handle_query(ctx: QueryContext):
    # SDK monitors elapsed time and sends heartbeats automatically
    answer = await ctx.auto_process(my_reasoning_engine.process(ctx.query))
    await ctx.reply(answer)

brain.run(host="0.0.0.0", port=8080)
```

> **Note:** If `heartbeat_after` and `hold_music_after` are both `None` (the default), `auto_process()` simply runs your coroutine with no monitoring overhead.

---

## Instant Acknowledgment & Heartbeats

### Instant Acknowledgment (Automatic)

HubUI's Voice Agent automatically speaks a brief acknowledgment to the caller the moment they ask a question — before your Brain receives the query. This means the caller is **never** left in silence, and you don't need to handle this yourself.

For example, when a caller asks *"Do you have any appointments tomorrow?"*, the Voice Agent immediately responds with something like *"Sure, let me check on that"* while your Brain processes the query in the background.

### Heartbeats (For Extended Processing)

Heartbeats are **follow-up** status updates that your Brain sends when processing takes longer than expected. Since the caller has already been acknowledged by the Voice Agent, heartbeat messages should provide **new** information — not repeat the initial acknowledgment.

Good heartbeat messages:
- *"Still searching — I'm checking a few more options for you."*
- *"Almost there — just confirming the details."*
- *"Thanks for your patience — I'm pulling up the latest availability."*

Avoid generic repeats of the initial acknowledgment (for example, *"Let me check on that"*) — the caller has already heard something similar from the Voice Agent.

### Using `auto_process()`

Configure timing thresholds once on `Brain` and `auto_process()` handles heartbeats automatically:

```python
brain = Brain(
    heartbeat_after=5.0,
    hold_music_after=15.0,
    heartbeat_message="Still working on that — just a bit longer.",
    hold_music_message="This is taking a little longer than usual. Please hold."
)

@brain.on_query()
async def handle(ctx: QueryContext):
    result = await ctx.auto_process(process_query(ctx.query))
    await ctx.reply(result)
```

**What happens from the caller's perspective:**

```
0s   → Caller asks a question
       Voice Agent instantly acknowledges: "Sure, let me check on that."
       Your Brain starts processing
5s   → Brain sends heartbeat: "Still working on that — just a bit longer."
15s  → Brain starts hold music: "This is taking a little longer than usual. Please hold."
20s  → Your coroutine returns → you call ctx.reply(result)
```

**Override timing per-call:**

```python
result = await ctx.auto_process(
    process_query(ctx.query),
    heartbeat_after=7.0,
    hold_music_after=20.0,
    heartbeat_message="Checking a few more sources for you...",
    hold_music_message="Still working — thanks for your patience."
)
```

**Full manual control (no auto timing):**

```python
brain = Brain()  # No timing configured

@brain.on_query()
async def handle(ctx: QueryContext):
    data = await fetch_from_database(ctx.query)
    if needs_extra_time(data):
        await ctx.say_processing("Still looking — checking a few more options.")
    if needs_even_more_time(data):
        await ctx.play_hold_music("This is taking a bit longer. Please hold.")
    result = await my_reasoning_layer(ctx.query, data)
    await ctx.reply(result)
```

---

## API Reference

### `Brain`

The main class. Instantiate once and register your handler.

```python
brain = Brain(
    api_key="br_xxx",         # Brain API key (or set HUBUI_BRAIN_API_KEY env var)
    heartbeat_after=None,     # Seconds before auto heartbeat in auto_process() (None = off)
    hold_music_after=None,    # Seconds before auto hold music in auto_process() (None = off)
    heartbeat_message=None,   # Message for auto heartbeat (default: "One moment please...")
    hold_music_message=None,  # Message for auto hold music (default: "This is taking a bit longer. Please hold...")
    debug=False,              # Log all WebSocket traffic
    shutdown_timeout=5.0      # Seconds to wait for active calls on shutdown
)
```

**API key lookup order:**
1. `api_key` constructor parameter
2. `HUBUI_BRAIN_API_KEY` environment variable

#### `brain.run()` / `brain.start()`

```python
# Blocking — recommended for standalone scripts
brain.run(host="0.0.0.0", port=8080)

# Async — for integration with an existing event loop
async def main():
    await brain.start(host="0.0.0.0", port=8080)

asyncio.run(main())
```

#### `@brain.on_query()`

Register your query handler. Called once per incoming query.

```python
@brain.on_query()
async def handle_query(ctx: QueryContext):
    await ctx.reply("Hello!")
```

---

### `QueryContext`

Passed to your handler on every query. Provides both the request data and all methods for responding.

#### Properties

| Property | Type | Description |
|---|---|---|
| `ctx.query` | `str` | The caller's current question or request |
| `ctx.session_id` | `str` | Unique identifier for this call session |
| `ctx.caller_number` | `str \| None` | Caller's phone number (E.164 format) |
| `ctx.business_number` | `str \| None` | The business phone number that received the call |
| `ctx.user_email` | `str \| None` | Caller's email address (web calls only) |
| `ctx.call_source` | `str` | Source of the call: `"sip"`, `"webrtc"`, or `"unknown"` (defaults to `"unknown"`) |
| `ctx.connection_type` | `str` | Interaction modality: `"voice"`, `"text"`, or `"unknown"` (defaults to `"unknown"`) |
| `ctx.history` | `List[ConversationTurn]` | All previous turns in this conversation |
| `ctx.total_turns` | `int` | Number of turns in `ctx.history` |
| `ctx.capabilities` | `Capabilities \| None` | Tools the Voice Agent supports |
| `ctx.available_tools` | `List[ToolDefinition]` | Flat list of supported tool names and descriptions |
| `ctx.is_complete` | `bool` | Whether a final response has already been sent |
| `ctx.request` | `QueryRequest` | The full raw request object |

#### Response Methods

Methods are either **non-final** (can be called multiple times before the final response) or **final** (ends the turn — no further responses can be sent after this).

```python
# ── Non-final (can call multiple times) ──────────────────────────────────

# Speak a follow-up status message during extended processing
# (The initial acknowledgment is already handled by the Voice Agent)
await ctx.say_processing("Still looking — checking a few more options.")

# Start playing hold music (for operations that take 15+ seconds)
await ctx.play_hold_music("This may take a moment. Please hold.")
await ctx.play_hold_music()  # Starts music without speaking a message first

# ── Final (ends the turn — call exactly once) ─────────────────────────────

# Successful answer
await ctx.reply("Your next available appointment is Thursday at 2 PM.")

# With optional structured data (for your own logging — not visible to the caller)
await ctx.reply("Thursday at 2 PM.", data={"appointment_id": "appt_123"})

# Ask the caller a clarifying question (triggers a new query with their answer)
await ctx.ask_clarification("Are you looking for a morning or afternoon time?")

# Respond with an error (caller hears the message; codes are for your logs only)
await ctx.reply_error(
    "I couldn't access the scheduling system right now. Please try again shortly.",
    error_code="CALENDAR_TIMEOUT",              # Optional: machine-readable, for logging
    error_details="Connection timed out after 30s"  # Optional: for debugging
)

# End the call (SIP only — always check has_tool first)
if ctx.has_tool("_terminate_call"):
    await ctx.terminate_call("Thank you for calling. Have a great day!")
```

#### Capability Checking

The Voice Agent advertises which tools it supports in each request. Always check before attempting to use a tool:

```python
# Check a specific tool
if ctx.has_tool("_terminate_call"):
    await ctx.terminate_call("Goodbye!")
else:
    await ctx.reply("Goodbye!")  # Graceful fallback

# Inspect all available tools
for tool in ctx.available_tools:
    print(f"{tool.name}: {tool.description}")
```

#### `auto_process()` Method

```python
result = await ctx.auto_process(
    coroutine,
    heartbeat_after=None,     # Override Brain-level default (seconds)
    hold_music_after=None,    # Override Brain-level default (seconds)
    heartbeat_message=None,   # Override Brain-level default
    hold_music_message=None   # Override Brain-level default
)
```

Wraps your coroutine and automatically sends follow-up heartbeat/hold music based on elapsed time. Per-call arguments override the Brain-level defaults. If no timing is configured anywhere, the coroutine runs directly.

> **Reminder:** The initial acknowledgment (e.g., *"Sure, let me check on that"*) is handled automatically by HubUI's Voice Agent. Heartbeats are follow-up messages for when processing takes longer than expected.

---

### `ConversationTurn`

Each item in `ctx.history`.

```python
for turn in ctx.history:
    print(f"{turn.role}: {turn.content}")  # role is "user" or "assistant"
    print(f"  at: {turn.timestamp}")       # ISO 8601 string, or None
```

---

## Getting Your API Key

Your Brain API key is generated automatically when you create a Brain in the HubUI dashboard.

1. Go to your HubUI dashboard and create a new Brain
2. Copy the API key shown at creation time
3. Provide it to your Brain backend:

```python
# Recommended: environment variable (keeps the key out of source code)
# export HUBUI_BRAIN_API_KEY=br_xxx
brain = Brain()

# Or pass directly
brain = Brain(api_key="br_xxx")
```

The SDK automatically includes this key in every response it sends. The Voice Agent validates it on every message received — keep it confidential and treat it like a password.

---

## Call Termination

Your Brain can instruct the Voice Agent to end the call. This capability is only available on SIP (phone) calls — always check with `ctx.has_tool()` before using it.

```python
@brain.on_query()
async def handle(ctx: QueryContext):
    result = await process_query(ctx.query)

    # Example: your logic determines the call should end
    if should_end_call(result):
        goodbye = result["goodbye_message"]
        if ctx.has_tool("_terminate_call"):
            await ctx.terminate_call(goodbye)
        else:
            await ctx.reply(goodbye)  # Graceful fallback for non-SIP calls
    else:
        await ctx.reply(result["answer"])
```

The Voice Agent speaks the message to the caller and then ends the call. From the caller's perspective the experience is seamless.

---

## Examples

### Simple Echo

```python
from hubui_brain import Brain, QueryContext

brain = Brain(debug=True)

@brain.on_query()
async def echo(ctx: QueryContext):
    await ctx.reply(f"You said: {ctx.query}")

brain.run(port=8080)
```

### OpenAI — Manual Heartbeats

```python
from hubui_brain import Brain, QueryContext
from openai import AsyncOpenAI

brain = Brain(debug=True)
client = AsyncOpenAI()

@brain.on_query()
async def handle(ctx: QueryContext):
    # Send a follow-up if needed (initial acknowledgment is handled by the Voice Agent)
    await ctx.say_processing("Still working on that — almost there.")

    messages = [{"role": t.role, "content": t.content} for t in ctx.history]
    messages.append({"role": "user", "content": ctx.query})

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    await ctx.reply(response.choices[0].message.content)

brain.run(port=8080)
```

### OpenAI — Auto Heartbeats

```python
from hubui_brain import Brain, QueryContext
from openai import AsyncOpenAI

brain = Brain(heartbeat_after=5.0, hold_music_after=15.0, debug=True)
client = AsyncOpenAI()

@brain.on_query()
async def handle(ctx: QueryContext):
    messages = [{"role": t.role, "content": t.content} for t in ctx.history]
    messages.append({"role": "user", "content": ctx.query})

    async def call_openai():
        resp = await client.chat.completions.create(
            model="gpt-4o", messages=messages
        )
        return resp.choices[0].message.content

    result = await ctx.auto_process(call_openai())

    if should_end_call(result):
        if ctx.has_tool("_terminate_call"):
            await ctx.terminate_call(result)
            return

    await ctx.reply(result)

brain.run(port=8080)
```

### LangGraph Agent

```python
from hubui_brain import Brain, QueryContext
from langgraph.graph import StateGraph

brain = Brain(debug=True)

graph = StateGraph(...)
agent = graph.compile()

@brain.on_query()
async def handle(ctx: QueryContext):
    await ctx.say_processing("Still pulling up the details...")

    result = await agent.ainvoke({
        "query": ctx.query,
        "history": [(t.role, t.content) for t in ctx.history],
        "caller": ctx.caller_number,
        "call_source": ctx.call_source,
    })

    await ctx.reply(result["response"])

brain.run(port=8080)
```

---

## Deployment

Your Brain is a standard async Python WebSocket server and runs on any platform that supports long-lived connections.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t my-brain .
docker run -p 8080:8080 -e HUBUI_BRAIN_API_KEY=br_xxx my-brain
```

### Connecting to HubUI

1. Deploy your Brain and note the public WebSocket URL (e.g. `wss://my-brain-xxx.brain.xyz`)
2. In the HubUI dashboard, create a Brain and enter that URL
3. Assign the Brain to your Agent
4. **Update your Agent's System Instructions to tell it when to call the Brain**

> **Important:** Connecting a Brain does not mean it's automatically used. Your Agent is autonomous — it handles all normal conversation on its own. The Brain is only invoked when your System Instructions explicitly tell the Agent to use it. For example: *"When the user asks about appointment availability, call the Brain to check the calendar."* Without these instructions, the Agent will never contact the Brain — even if one is connected.

HubUI handles all the routing and real-time management from there.

---

## Debug Mode

Enable with `debug=True` to see all message traffic in your console:

```
════════════════════════════════════════════════════════════
10:30:15.123 🎭 AGENT → 🧠 BRAIN [call-_+15551234567_abc123]
Query: "What appointments are available tomorrow?"
{
  "type": "query",
  "session_id": "call-_+15551234567_abc123",
  "current_query": "What appointments are available tomorrow?",
  "caller_number": "+15551234567",
  "call_source": "sip",
  ...
}
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
10:30:15.456 🧠 BRAIN → 🎭 AGENT [call-_+15551234567_abc123]
[PROCESSING] "Let me check the calendar..."
────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────
10:30:17.890 🧠 BRAIN → 🎭 AGENT [call-_+15551234567_abc123]
[SUCCESS] "We have openings at 9 AM, 1 PM, and 3 PM tomorrow."
────────────────────────────────────────────────────────────
```

When auto heartbeats fire, you'll also see timing events:

```
⏱️ Auto heartbeat at 5.0s: One moment please...
⏱️ Auto hold music at 15.0s: This is taking a bit longer. Please hold...
```

## Version History

| Version | Changes |
|---|---|
| 0.1.0 | Initial release — capabilities, call termination, and `auto_process()` for automatic heartbeat management |

---

## License

Apache 2.0

---

## Get Started

- **[Sign up free](https://app.hubui.ai)** — create your first Voice Agent in minutes
- **[Read the docs](https://app.hubui.ai/documentation)** — full platform documentation
- **[Join the Discord](https://discord.gg/9HZBN6ZeU6)** — get help, share what you're building

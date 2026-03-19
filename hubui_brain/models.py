"""
Message models for HubUI Brain.

Pure dataclasses for request/response messages between the Voice Agent
and the Brain backend. No external dependencies - uses stdlib only.

Protocol Version: 1.0.0
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Protocol version
PROTOCOL_VERSION = "1.0.0"

# Header name for Brain API key (must match Voice Agent's expectation)
BRAIN_KEY_HEADER = "X-HubUI-BR-Key"


# =============================================================================
# CAPABILITIES MODELS (Protocol v1.0.0)
# =============================================================================

@dataclass
class ToolDefinition:
    """
    Definition of a tool the Voice Agent can execute.

    Attributes:
        name: Tool identifier (e.g., "_heartbeat", "_terminate_call")
        description: Human-readable description of what the tool does
    """
    name: str
    description: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
        }


@dataclass
class AgentInfo:
    """
    Information about the Voice Agent.

    Attributes:
        type: Agent type (e.g., "conversational")
        modality: Supported modalities (e.g., ["voice", "text"])
        version: Agent version
    """
    type: str = "conversational"
    modality: List[str] = field(default_factory=lambda: ["voice", "text"])
    version: str = "1.0.0"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "conversational"),
            modality=data.get("modality", ["voice", "text"]),
            version=data.get("version", "1.0.0"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "modality": self.modality,
            "version": self.version,
        }


@dataclass
class Capabilities:
    """
    Voice Agent capabilities advertised in each request.

    Backends can use this to know what tools are available and
    adjust their responses accordingly.

    Attributes:
        agent: Information about the Voice Agent
        tools: List of tools the Voice Agent can execute
        protocol_version: Protocol version for compatibility
    """
    agent: AgentInfo = field(default_factory=AgentInfo)
    tools: List[ToolDefinition] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capabilities":
        """Create from dictionary."""
        agent_data = data.get("agent", {})
        tools_data = data.get("tools", [])
        return cls(
            agent=AgentInfo.from_dict(agent_data),
            tools=[ToolDefinition.from_dict(t) for t in tools_data],
            protocol_version=data.get("protocol_version", PROTOCOL_VERSION),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent": self.agent.to_dict(),
            "tools": [t.to_dict() for t in self.tools],
            "protocol_version": self.protocol_version,
        }

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available."""
        return any(t.name == name for t in self.tools)


# =============================================================================
# CONVERSATION MODELS
# =============================================================================

@dataclass
class ConversationTurn:
    """
    A single turn in the conversation history.

    Attributes:
        role: Either "user" or "assistant"
        content: The spoken text
        timestamp: When this turn occurred (ISO 8601 format)
    """
    role: str
    content: str
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        """Create a conversation turn.

        Args:
            role: Either ``"user"`` or ``"assistant"``.
            content: The spoken text for this turn.
            timestamp: When this turn occurred (ISO 8601 string, or ``None``).
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (JSON serialization)."""
        result = {
            "role": self.role,
            "content": self.content,
        }
        if self.timestamp:
            result["timestamp"] = self.timestamp
        return result


@dataclass
class QueryRequest:
    """
    Incoming query request from the Voice Agent.

    This contains the full conversation context needed to process
    the user's current query.

    Attributes:
        type: Message type (always "query" for query requests)
        session_id: Unique call identifier
        current_query: The user's current question/request
        conversation_history: Previous turns in the conversation
        caller_number: Phone number of the caller (E.164 format)
        business_number: Business phone number that received the call
        user_email: Email of the user (WebRTC calls only)
        connection_type: Interaction modality ("voice", "text", or "unknown"; defaults to "unknown")
        call_source: Source of the call ("sip", "webrtc", or "unknown")
        timestamp: When the request was sent (ISO 8601)
        total_turns: Number of items in conversation_history
        capabilities: Voice Agent capabilities (Protocol v1.0.0)
    """
    type: str = "query"  # Message type identifier
    session_id: str = ""
    current_query: str = ""
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    caller_number: Optional[str] = None
    business_number: Optional[str] = None
    user_email: Optional[str] = None  # WebRTC calls only
    connection_type: str = "unknown"  # "voice", "text", or "unknown"
    call_source: str = "unknown"  # "sip", "webrtc", or "unknown"
    timestamp: Optional[str] = None
    total_turns: int = 0
    capabilities: Optional[Capabilities] = None  # Protocol v1.0.0

    def __post_init__(self) -> None:
        """Create a query request.

        Args:
            type: Message type (always ``"query"``).
            session_id: Unique call identifier.
            current_query: The user's current question or request.
            conversation_history: Previous turns in the conversation.
            caller_number: Phone number of the caller (E.164 format).
            business_number: Business phone number that received the call.
            user_email: Email of the user (WebRTC calls only).
            connection_type: Interaction modality (``"voice"``, ``"text"``, or ``"unknown"``).
            call_source: Source of the call (``"sip"``, ``"webrtc"``, or ``"unknown"``).
            timestamp: When the request was sent (ISO 8601).
            total_turns: Number of items in conversation_history.
            capabilities: Voice Agent capabilities (Protocol v1.0.0).
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryRequest":
        """Create from dictionary (JSON deserialization)."""
        history = [
            ConversationTurn.from_dict(turn)
            for turn in data.get("conversation_history", [])
        ]

        # Parse capabilities if present (Protocol v1.0.0)
        capabilities = None
        if "capabilities" in data and data["capabilities"]:
            capabilities = Capabilities.from_dict(data["capabilities"])

        return cls(
            type=data.get("type", "query"),
            session_id=data.get("session_id", ""),
            current_query=data.get("current_query", ""),
            conversation_history=history,
            caller_number=data.get("caller_number"),
            business_number=data.get("business_number"),
            user_email=data.get("user_email"),
            connection_type=data.get("connection_type", "unknown"),
            call_source=data.get("call_source", "unknown"),
            timestamp=data.get("timestamp"),
            total_turns=data.get("total_turns", len(history)),
            capabilities=capabilities,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "QueryRequest":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (JSON serialization)."""
        result: Dict[str, Any] = {
            "type": self.type,
            "session_id": self.session_id,
            "current_query": self.current_query,
            "conversation_history": [turn.to_dict() for turn in self.conversation_history],
            "caller_number": self.caller_number,
            "business_number": self.business_number,
            "connection_type": self.connection_type,
            "call_source": self.call_source,
            "timestamp": self.timestamp,
            "total_turns": self.total_turns,
        }
        if self.user_email:
            result["user_email"] = self.user_email
        if self.capabilities:
            result["capabilities"] = self.capabilities.to_dict()
        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available in capabilities."""
        if not self.capabilities:
            return False
        return self.capabilities.has_tool(name)


# =============================================================================
# RESPONSE BUILDERS
# =============================================================================

def build_processing_response(
    message: Optional[str] = None,
    play_hold_music: bool = False
) -> Dict[str, Any]:
    """
    Build a processing (heartbeat) response.

    Args:
        message: Optional message for the agent to speak
        play_hold_music: If True, agent starts playing hold music

    Returns:
        Dictionary ready for JSON serialization
    """
    response: Dict[str, Any] = {"status": "processing"}
    if message:
        response["message"] = message
    if play_hold_music:
        response["play_hold_music"] = True
    return response


def build_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    tool: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a success response.

    Args:
        message: The response for the agent to speak
        data: Optional structured data (for logging/debugging)
        tool: Optional tool for the agent to execute (Protocol v1.0.0)
              e.g., "_heartbeat", "_heartbeat_music", "_terminate_call"

    Returns:
        Dictionary ready for JSON serialization
    """
    response: Dict[str, Any] = {
        "status": "success",
        "message": message,
    }
    if data:
        response["data"] = data
    if tool:
        response["tool"] = tool
    return response


def build_clarification_response(message: str) -> Dict[str, Any]:
    """
    Build a needs_clarification response.

    Args:
        message: The clarification question to ask the user

    Returns:
        Dictionary ready for JSON serialization
    """
    return {
        "status": "needs_clarification",
        "message": message,
    }


def build_error_response(
    message: str,
    error_code: Optional[str] = None,
    error_details: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build an error response.

    Args:
        message: User-friendly error message for agent to speak
        error_code: Machine-readable error code (for logging)
        error_details: Technical details (for debugging)

    Returns:
        Dictionary ready for JSON serialization
    """
    response: Dict[str, Any] = {
        "status": "error",
        "message": message,
    }
    if error_code:
        response["error_code"] = error_code
    if error_details:
        response["error_details"] = error_details
    return response


# =============================================================================
# TOOL RESPONSE BUILDERS (Protocol v1.0.0)
# =============================================================================

def build_tool_response(
    tool: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a response that triggers a tool on the Voice Agent.

    This is a convenience function that builds a success response
    with a tool invocation. The Voice Agent will speak the message
    and then execute the tool.

    Available tools (Protocol v1.0.0):
        - "_terminate_call": End the call gracefully (SIP only).
                             Check ctx.has_tool("_terminate_call") before using.

    NOTE: Do NOT use this function for heartbeats or hold music.
    Sending "_heartbeat" or "_heartbeat_music" via build_tool_response produces
    a final (status: success) response that terminates the query loop — the Voice
    Agent will speak the message and return to the LLM, NOT continue processing.
    For in-progress status updates use the dedicated methods instead:
        - ctx.say_processing(message)  → sends status: processing heartbeat
        - ctx.play_hold_music(message) → sends status: processing + hold music

    Args:
        tool: Tool name. Currently only "_terminate_call" is supported.
        message: Message for the agent to speak before executing the tool
        data: Optional structured data

    Returns:
        Dictionary ready for JSON serialization

    Example:
        # End the call after saying goodbye
        response = build_tool_response(
            tool="_terminate_call",
            message="Thank you for calling. Goodbye!"
        )
    """
    return build_success_response(message=message, data=data, tool=tool)

"""
Debug logging for HubUI Brain.

Provides formatted logging of all WebSocket messages with:
- Direction indicators (AGENT → BRAIN, BRAIN → AGENT)
- Pretty-printed JSON
- Timestamps
- Session ID tracking
- Optional color output
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class BrainDebugger:
    """
    Debug logger for HubUI Brain WebSocket traffic.

    Logs all incoming and outgoing messages with formatting
    to help developers understand the message flow.

    Attributes:
        enabled: Whether debug logging is active
        use_colors: Whether to use ANSI colors (auto-detected)
        show_timestamps: Whether to include timestamps
    """

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "magenta": "\033[35m",
        "blue": "\033[34m",
    }

    def __init__(
        self,
        enabled: bool = False,
        use_colors: Optional[bool] = None,
        show_timestamps: bool = True
    ):
        """
        Initialize the debugger.

        Args:
            enabled: Whether to enable debug output
            use_colors: Use ANSI colors. None = auto-detect TTY
            show_timestamps: Include timestamps in output
        """
        self.enabled = enabled
        self.show_timestamps = show_timestamps

        # Auto-detect color support
        if use_colors is None:
            self.use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        else:
            self.use_colors = use_colors

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        if not self.show_timestamps:
            return ""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3] + " "

    def _format_json(self, data: Dict[str, Any]) -> str:
        """Pretty-format JSON data."""
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def log_incoming(
        self,
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """
        Log an incoming message from the Voice Agent.

        Args:
            data: The parsed JSON message
            session_id: Session ID for context (extracted from data if not provided)
        """
        if not self.enabled:
            return

        session_id = session_id or data.get("session_id", "unknown")

        # Header
        header = self._color("═" * 60, "cyan")
        direction = self._color("🎭 AGENT → 🧠 BRAIN", "cyan")
        session = self._color(f"[{session_id}]", "dim")
        timestamp = self._color(self._timestamp(), "dim")

        # Message type
        query = data.get("current_query", "")
        if len(query) > 50:
            query = query[:50] + "..."
        msg_type = self._color(f"Query: \"{query}\"", "bold")

        print(f"\n{header}")
        print(f"{timestamp}{direction} {session}")
        print(f"{msg_type}")
        print(self._color(self._format_json(data), "dim"))
        print(header)

    def log_outgoing(
        self,
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> None:
        """
        Log an outgoing message to the Voice Agent.

        Args:
            data: The response dictionary
            session_id: Session ID for context
        """
        if not self.enabled:
            return

        status = data.get("status", "unknown")

        # Color based on status
        status_colors = {
            "processing": "yellow",
            "success": "green",
            "needs_clarification": "magenta",
            "error": "red",
        }
        color = status_colors.get(status, "blue")

        # Header
        header = self._color("─" * 60, color)
        direction = self._color("🧠 BRAIN → 🎭 AGENT", color)
        session = self._color(f"[{session_id or 'unknown'}]", "dim")
        timestamp = self._color(self._timestamp(), "dim")

        # Status badge
        status_badge = self._color(f"[{status.upper()}]", color)

        # Message preview
        message = data.get("message", "")
        if len(message) > 50:
            message = message[:50] + "..."
        msg_preview = self._color(f'"{message}"', "bold") if message else ""

        print(f"\n{header}")
        print(f"{timestamp}{direction} {session}")
        print(f"{status_badge} {msg_preview}")
        print(self._color(self._format_json(data), "dim"))
        print(header)

    def log_connection(self, session_id: str, event: str) -> None:
        """
        Log a connection event.

        Args:
            session_id: The session identifier
            event: Event type (connected, disconnected, error)
        """
        if not self.enabled:
            return

        timestamp = self._color(self._timestamp(), "dim")

        if event == "connected":
            icon = self._color("🔌", "green")
            text = self._color(f"Connection opened [{session_id}]", "green")
        elif event == "disconnected":
            icon = self._color("🔌", "yellow")
            text = self._color(f"Connection closed [{session_id}]", "yellow")
        elif event == "error":
            icon = self._color("❌", "red")
            text = self._color(f"Connection error [{session_id}]", "red")
        else:
            icon = "ℹ️"
            text = f"{event} [{session_id}]"

        print(f"{timestamp}{icon} {text}")

    def log_server(self, message: str, level: str = "info") -> None:
        """
        Log a server-level message.

        Args:
            message: The message to log
            level: Log level (info, warning, error)
        """
        if not self.enabled:
            return

        timestamp = self._color(self._timestamp(), "dim")

        level_styles = {
            "info": ("ℹ️", "blue"),
            "warning": ("⚠️", "yellow"),
            "error": ("❌", "red"),
            "success": ("✅", "green"),
        }

        icon, color = level_styles.get(level, ("•", "dim"))
        text = self._color(message, color)

        print(f"{timestamp}{icon} {text}")


# Global debugger instance (can be replaced)
_debugger: Optional[BrainDebugger] = None


def get_debugger() -> BrainDebugger:
    """Get the global debugger instance."""
    global _debugger
    if _debugger is None:
        _debugger = BrainDebugger(enabled=False)
    return _debugger


def set_debugger(debugger: BrainDebugger) -> None:
    """Set the global debugger instance."""
    global _debugger
    _debugger = debugger

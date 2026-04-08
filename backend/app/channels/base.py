"""Channel base class for third-party IM bot integrations."""

from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request


class ChannelBase(ABC):
    """Abstract base for all channel integrations (WeChat Work, DingTalk, etc.)."""

    name: str  # unique identifier, e.g. "wechat_work"
    display_name: str  # human-readable, e.g. "企业微信"

    @abstractmethod
    async def handle_message(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Process incoming message from the channel.

        Returns a dict with at least:
          - channel_user_id: str
          - content: str
          - message_type: str (text, markdown, etc.)
        """

    @abstractmethod
    async def send_message(self, channel_user_id: str, content: str, msg_type: str = "text") -> bool:
        """Send message to a user via this channel.

        Returns True if the message was sent successfully.
        """

    @abstractmethod
    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify webhook signature from the channel platform."""

    def is_configured(self) -> bool:
        """Check if the channel has required credentials configured."""
        return False

    def get_status(self) -> dict[str, Any]:
        """Return channel status info."""
        configured = self.is_configured()
        return {
            "name": self.name,
            "display_name": self.display_name,
            "configured": configured,
            "status": "ready" if configured else "not_configured",
        }

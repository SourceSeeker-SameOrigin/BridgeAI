"""Channel Manager — central registry for all channel integrations.

Responsibilities:
  - Auto-discover configured channels from environment
  - Route incoming messages to chat_service
  - Send replies back via the correct channel
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelBase
from app.channels.dingtalk_bot import DingTalkChannel
from app.channels.feishu_bot import FeishuChannel
from app.channels.wechat_work import WeChatWorkChannel

logger = logging.getLogger(__name__)


class ChannelManager:
    """Singleton-style manager for all channel integrations."""

    def __init__(self) -> None:
        self._channels: dict[str, ChannelBase] = {}
        self._register_channels()

    def _register_channels(self) -> None:
        """Register all known channel implementations."""
        channels: list[ChannelBase] = [
            WeChatWorkChannel(),
            DingTalkChannel(),
            FeishuChannel(),
        ]
        for ch in channels:
            self._channels[ch.name] = ch
            status = "configured" if ch.is_configured() else "not_configured"
            logger.info("Channel registered: %s (%s) — %s", ch.name, ch.display_name, status)

    def get_channel(self, name: str) -> ChannelBase | None:
        """Get a channel by name."""
        return self._channels.get(name)

    def list_channels(self) -> list[dict[str, Any]]:
        """Return status of all registered channels."""
        return [ch.get_status() for ch in self._channels.values()]

    async def route_message_to_chat(
        self,
        channel_name: str,
        channel_user_id: str,
        content: str,
        db: AsyncSession,
        *,
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """Route an incoming channel message to chat_service and return the reply.

        This creates a non-streaming chat request using a system user,
        then returns the assistant reply text.
        """
        from app.schemas.chat import ChatRequest
        from app.services.chat_service import process_chat_sync

        if not content.strip():
            return "收到空消息，请输入您的问题。"

        # Build a ChatRequest from the channel message
        request = ChatRequest(message=content, stream=False)

        # Use a deterministic "channel bot" user_id derived from channel info
        # In production, map channel_user_id to actual users
        bot_user_id = f"channel:{channel_name}:{channel_user_id}"

        try:
            result = await process_chat_sync(
                request=request,
                db=db,
                user_id=bot_user_id,
            )
            return result.get("content", "处理失败，请稍后重试。")
        except Exception as e:
            logger.error("Channel chat routing error: %s", e, exc_info=True)
            return f"处理消息时出错：{e}"

    async def send_reply(
        self,
        channel_name: str,
        channel_user_id: str,
        content: str,
        msg_type: str = "text",
        *,
        session_webhook: str | None = None,
    ) -> bool:
        """Send a reply via the specified channel."""
        channel = self.get_channel(channel_name)
        if channel is None:
            logger.error("Unknown channel: %s", channel_name)
            return False

        if not channel.is_configured():
            logger.warning("Channel %s not configured, cannot send", channel_name)
            return False

        # DingTalk: prefer session webhook for in-conversation reply
        if channel_name == "dingtalk" and session_webhook:
            dingtalk_ch: DingTalkChannel = channel  # type: ignore[assignment]
            return await dingtalk_ch.reply_via_webhook(session_webhook, content, msg_type)

        return await channel.send_message(channel_user_id, content, msg_type)


# Module-level singleton
channel_manager = ChannelManager()

"""DingTalk (钉钉) bot channel integration.

Implements:
  - Webhook callback signature verification (HMAC-SHA256)
  - Incoming text message parsing
  - Outgoing message via DingTalk robot webhook (text & markdown)
  - Access token management for DingTalk Open API

References:
  - https://open.dingtalk.com/document/orgapp/receive-message
  - https://open.dingtalk.com/document/orgapp/robot-reply-and-proactive-message
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx
from fastapi import Request

from app.channels.base import ChannelBase
from app.config import settings

logger = logging.getLogger(__name__)

# DingTalk API base URL
_API_BASE = "https://api.dingtalk.com"
_OLD_API_BASE = "https://oapi.dingtalk.com"

# Access token cache
_access_token: str = ""
_token_expires_at: float = 0.0


class DingTalkChannel(ChannelBase):
    """DingTalk bot channel."""

    name = "dingtalk"
    display_name = "钉钉"

    def __init__(self) -> None:
        self._app_key = settings.DINGTALK_APP_KEY
        self._app_secret = settings.DINGTALK_APP_SECRET
        self._robot_code = settings.DINGTALK_ROBOT_CODE

    def is_configured(self) -> bool:
        return bool(self._app_key and self._app_secret)

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify DingTalk callback signature.

        DingTalk sends timestamp and sign in headers.
        sign = Base64(HMAC-SHA256(app_secret, timestamp + "\\n" + app_secret))
        """
        timestamp = request.headers.get("timestamp", "")
        sign = request.headers.get("sign", "")

        if not timestamp or not sign:
            return False

        # Replay-attack window — DingTalk's official guidance is ≤1 hour, but a
        # tighter 5-minute window is industry standard and dramatically narrows
        # the attack surface for leaked signatures without breaking legitimate calls.
        try:
            ts = int(timestamp)
            now = int(time.time() * 1000)
            if abs(now - ts) > 300 * 1000:
                logger.warning("DingTalk signature timestamp expired")
                return False
        except (ValueError, TypeError):
            return False

        # Compute expected signature
        string_to_sign = f"{timestamp}\n{self._app_secret}"
        hmac_code = hmac.new(
            self._app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode("utf-8")

        return hmac.compare_digest(sign, expected_sign)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_message(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Parse incoming DingTalk message.

        DingTalk robot callback payload structure:
        {
            "msgtype": "text",
            "text": {"content": "..."},
            "senderStaffId": "...",
            "senderNick": "...",
            "conversationId": "...",
            "sessionWebhook": "...",
            ...
        }
        """
        msg_type = raw_payload.get("msgtype", "")
        sender_id = raw_payload.get("senderStaffId", "") or raw_payload.get("senderId", "")
        sender_nick = raw_payload.get("senderNick", "")
        conversation_id = raw_payload.get("conversationId", "")
        session_webhook = raw_payload.get("sessionWebhook", "")

        content = ""
        if msg_type == "text":
            text_obj = raw_payload.get("text", {})
            content = text_obj.get("content", "").strip()
        elif msg_type == "richText":
            rich_text = raw_payload.get("content", {}).get("richText", [])
            parts = [item.get("text", "") for item in rich_text if "text" in item]
            content = "".join(parts).strip()

        return {
            "channel_user_id": sender_id,
            "content": content,
            "message_type": msg_type,
            "sender_nick": sender_nick,
            "conversation_id": conversation_id,
            "session_webhook": session_webhook,
        }

    async def send_message(self, channel_user_id: str, content: str, msg_type: str = "text") -> bool:
        """Send message to user via DingTalk robot API.

        Uses the new Open API for proactive messaging.
        """
        if not self.is_configured():
            logger.warning("DingTalk channel not configured, skipping send")
            return False

        token = await self._get_access_token()
        if not token:
            return False

        url = f"{_OLD_API_BASE}/topapi/message/corpconversation/asyncsend_v2?access_token={token}"

        if msg_type == "markdown":
            payload = {
                "agent_id": self._robot_code,
                "userid_list": channel_user_id,
                "msg": {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "BridgeAI",
                        "text": content,
                    },
                },
            }
        else:
            payload = {
                "agent_id": self._robot_code,
                "userid_list": channel_user_id,
                "msg": {
                    "msgtype": "text",
                    "text": {
                        "content": content,
                    },
                },
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                result = resp.json()
                if result.get("errcode", -1) != 0:
                    logger.error("DingTalk send failed: %s", result.get("errmsg"))
                    return False
                return True
        except Exception as e:
            logger.error("DingTalk send error: %s", e)
            return False

    async def reply_via_webhook(self, session_webhook: str, content: str, msg_type: str = "text") -> bool:
        """Reply via DingTalk session webhook (within conversation context).

        This is simpler and preferred when session_webhook is available.
        """
        if not session_webhook:
            return False

        if msg_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "BridgeAI",
                    "text": content,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": content},
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(session_webhook, json=payload)
                result = resp.json()
                if result.get("errcode", -1) != 0:
                    logger.error("DingTalk webhook reply failed: %s", result.get("errmsg"))
                    return False
                return True
        except Exception as e:
            logger.error("DingTalk webhook reply error: %s", e)
            return False

    # ------------------------------------------------------------------
    # Access Token
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str:
        """Get or refresh DingTalk access token."""
        global _access_token, _token_expires_at

        if _access_token and time.time() < _token_expires_at:
            return _access_token

        url = f"{_OLD_API_BASE}/gettoken"
        params = {"appkey": self._app_key, "appsecret": self._app_secret}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
                if result.get("errcode", -1) != 0:
                    logger.error("Failed to get DingTalk token: %s", result.get("errmsg"))
                    return ""
                _access_token = result["access_token"]
                _token_expires_at = time.time() + result.get("expires_in", 7200) - 300
                return _access_token
        except Exception as e:
            logger.error("DingTalk token request error: %s", e)
            return ""

"""Feishu (飞书) bot channel integration.

Implements:
  - Event subscription verification (challenge-response)
  - Incoming text message parsing
  - Outgoing message via Feishu Open API
  - Tenant access token management

References:
  - https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure
  - https://open.feishu.cn/document/server-docs/im-v1/message/create
"""

import hashlib
import logging
import time
from typing import Any

import httpx
from fastapi import Request

from app.channels.base import ChannelBase
from app.config import settings

logger = logging.getLogger(__name__)

_FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# Tenant access token cache
_tenant_access_token: str = ""
_token_expires_at: float = 0.0


class FeishuChannel(ChannelBase):
    """Feishu bot channel."""

    name = "feishu"
    display_name = "飞书"

    def __init__(self) -> None:
        self._app_id = settings.FEISHU_APP_ID
        self._app_secret = settings.FEISHU_APP_SECRET
        self._verification_token = settings.FEISHU_VERIFICATION_TOKEN
        self._encrypt_key = settings.FEISHU_ENCRYPT_KEY

    def is_configured(self) -> bool:
        return bool(self._app_id and self._app_secret)

    # ------------------------------------------------------------------
    # Signature / verification
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify Feishu event callback signature.

        Feishu uses X-Lark-Signature header:
        signature = sha256(timestamp + nonce + encrypt_key + body)
        """
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")

        if not all([timestamp, nonce, signature]):
            # If no signature headers, skip verification (e.g. challenge request)
            return True

        bytes_to_sign = (timestamp + nonce + self._encrypt_key).encode("utf-8") + body
        expected = hashlib.sha256(bytes_to_sign).hexdigest()
        return expected == signature

    def handle_url_verification(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Handle Feishu URL verification challenge.

        Feishu sends: {"challenge": "xxx", "token": "xxx", "type": "url_verification"}
        We must return: {"challenge": "xxx"}
        """
        if payload.get("type") != "url_verification":
            return None

        token = payload.get("token", "")
        if self._verification_token and token != self._verification_token:
            logger.warning("Feishu verification token mismatch")
            return None

        return {"challenge": payload.get("challenge", "")}

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_message(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Parse incoming Feishu event message.

        Event v2 structure:
        {
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1", ...},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xxx"}},
                "message": {
                    "message_type": "text",
                    "content": "{\"text\": \"hello\"}"
                }
            }
        }
        """
        event = raw_payload.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id", "")
        message = event.get("message", {})
        msg_type = message.get("message_type", "")
        chat_id = message.get("chat_id", "")

        content = ""
        if msg_type == "text":
            import json
            try:
                content_json = json.loads(message.get("content", "{}"))
                content = content_json.get("text", "").strip()
            except (json.JSONDecodeError, TypeError):
                content = ""

        return {
            "channel_user_id": open_id,
            "content": content,
            "message_type": msg_type,
            "chat_id": chat_id,
        }

    async def send_message(
        self, channel_user_id: str, content: str, msg_type: str = "text"
    ) -> bool:
        """Send message to user via Feishu Open API."""
        if not self.is_configured():
            logger.warning("Feishu channel not configured, skipping send")
            return False

        token = await self._get_tenant_access_token()
        if not token:
            return False

        url = f"{_FEISHU_API_BASE}/im/v1/messages"
        params = {"receive_id_type": "open_id"}

        import json

        if msg_type == "text":
            payload = {
                "receive_id": channel_user_id,
                "msg_type": "text",
                "content": json.dumps({"text": content}),
            }
        else:
            payload = {
                "receive_id": channel_user_id,
                "msg_type": "text",
                "content": json.dumps({"text": content}),
            }

        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url, json=payload, params=params, headers=headers
                )
                result = resp.json()
                if result.get("code", -1) != 0:
                    logger.error(
                        "Feishu send failed: %s", result.get("msg", "unknown error")
                    )
                    return False
                return True
        except Exception as e:
            logger.error("Feishu send error: %s", e)
            return False

    # ------------------------------------------------------------------
    # Tenant Access Token
    # ------------------------------------------------------------------

    async def _get_tenant_access_token(self) -> str:
        """Get or refresh Feishu tenant access token."""
        global _tenant_access_token, _token_expires_at

        if _tenant_access_token and time.time() < _token_expires_at:
            return _tenant_access_token

        url = f"{_FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self._app_id, "app_secret": self._app_secret}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                result = resp.json()
                if result.get("code", -1) != 0:
                    logger.error(
                        "Failed to get Feishu token: %s",
                        result.get("msg", "unknown"),
                    )
                    return ""
                _tenant_access_token = result.get("tenant_access_token", "")
                expire = result.get("expire", 7200)
                _token_expires_at = time.time() + expire - 300
                return _tenant_access_token
        except Exception as e:
            logger.error("Feishu token request error: %s", e)
            return ""

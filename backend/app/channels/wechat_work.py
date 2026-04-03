"""WeChat Work (企业微信) bot channel integration.

Implements:
  - Webhook callback signature verification (URL verification & message push)
  - Incoming text message parsing (XML payload decrypted via WXBizMsgCrypt)
  - Outgoing message via WeChat Work API (text & markdown)
  - Access token management with auto-refresh

References:
  - https://developer.work.weixin.qq.com/document/path/90238
  - https://developer.work.weixin.qq.com/document/path/90236
"""

import base64
import hashlib
import hmac
import logging
import socket
import struct
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import Request

from app.channels.base import ChannelBase
from app.config import settings

logger = logging.getLogger(__name__)

# WeChat Work API base URL
_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

# Access token cache
_access_token: str = ""
_token_expires_at: float = 0.0


class WeChatWorkChannel(ChannelBase):
    """WeChat Work bot channel."""

    name = "wechat_work"
    display_name = "企业微信"

    def __init__(self) -> None:
        self._corp_id = settings.WECHAT_WORK_CORP_ID
        self._agent_id = settings.WECHAT_WORK_AGENT_ID
        self._secret = settings.WECHAT_WORK_SECRET
        self._token = settings.WECHAT_WORK_TOKEN
        self._encoding_aes_key = settings.WECHAT_WORK_ENCODING_AES_KEY

    def is_configured(self) -> bool:
        return bool(
            self._corp_id
            and self._secret
            and self._token
            and self._encoding_aes_key
        )

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(self, request: Request, body: bytes) -> bool:
        """Verify WeChat Work callback signature.

        WeChat Work sends: msg_signature, timestamp, nonce as query params.
        Signature = SHA1(sort([token, timestamp, nonce, encrypt]))
        """
        params = request.query_params
        msg_signature = params.get("msg_signature", "")
        timestamp = params.get("timestamp", "")
        nonce = params.get("nonce", "")

        # For URL verification, echostr is in query params
        echostr = params.get("echostr", "")

        # For message push, encrypt is in the XML body
        encrypt = echostr
        if body:
            try:
                root = ET.fromstring(body.decode("utf-8"))
                encrypt_node = root.find("Encrypt")
                if encrypt_node is not None and encrypt_node.text:
                    encrypt = encrypt_node.text
            except ET.ParseError:
                pass

        if not encrypt:
            return False

        sort_list = sorted([self._token, timestamp, nonce, encrypt])
        sha1_str = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
        return sha1_str == msg_signature

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_message(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Parse incoming WeChat Work message.

        The raw_payload should contain:
          - xml_body: the decrypted XML string
          OR
          - encrypted_body: raw XML with <Encrypt> node (we decrypt it)
        """
        xml_body = raw_payload.get("xml_body", "")

        if not xml_body and "encrypted_body" in raw_payload:
            xml_body = self._decrypt_message(raw_payload["encrypted_body"])

        if not xml_body:
            return {"channel_user_id": "", "content": "", "message_type": "unknown"}

        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError:
            logger.warning("Failed to parse WeChat Work XML message")
            return {"channel_user_id": "", "content": "", "message_type": "unknown"}

        msg_type = root.findtext("MsgType", "")
        from_user = root.findtext("FromUserName", "")
        content = ""

        if msg_type == "text":
            content = root.findtext("Content", "")
        elif msg_type == "event":
            event_type = root.findtext("Event", "")
            event_key = root.findtext("EventKey", "")
            content = f"[event:{event_type}] {event_key}"

        return {
            "channel_user_id": from_user,
            "content": content,
            "message_type": msg_type,
            "raw_xml": xml_body,
        }

    async def send_message(self, channel_user_id: str, content: str, msg_type: str = "text") -> bool:
        """Send message to user via WeChat Work API."""
        if not self.is_configured():
            logger.warning("WeChat Work channel not configured, skipping send")
            return False

        token = await self._get_access_token()
        if not token:
            return False

        url = f"{_API_BASE}/message/send?access_token={token}"

        if msg_type == "markdown":
            payload = {
                "touser": channel_user_id,
                "msgtype": "markdown",
                "agentid": int(self._agent_id) if self._agent_id else 0,
                "markdown": {"content": content},
            }
        else:
            payload = {
                "touser": channel_user_id,
                "msgtype": "text",
                "agentid": int(self._agent_id) if self._agent_id else 0,
                "text": {"content": content},
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                result = resp.json()
                if result.get("errcode", -1) != 0:
                    logger.error("WeChat Work send failed: %s", result.get("errmsg"))
                    return False
                return True
        except Exception as e:
            logger.error("WeChat Work send error: %s", e)
            return False

    # ------------------------------------------------------------------
    # URL verification (GET callback)
    # ------------------------------------------------------------------

    def handle_url_verification(self, request: Request) -> str | None:
        """Handle WeChat Work URL verification (GET request).

        Returns decrypted echostr to complete verification, or None on failure.
        """
        params = request.query_params
        echostr = params.get("echostr", "")
        if not echostr or not self.verify_signature(request, b""):
            return None
        return self._decrypt_echostr(echostr)

    # ------------------------------------------------------------------
    # Encryption / Decryption
    # ------------------------------------------------------------------

    def _get_aes_key(self) -> bytes:
        """Decode encoding_aes_key to 32-byte AES key."""
        return base64.b64decode(self._encoding_aes_key + "=")

    def _decrypt_echostr(self, echostr: str) -> str:
        """Decrypt the echostr from URL verification."""
        try:
            aes_key = self._get_aes_key()
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
            decryptor = cipher.decryptor()
            encrypted = base64.b64decode(echostr)
            decrypted = decryptor.update(encrypted) + decryptor.finalize()
            # Remove PKCS7 padding
            pad_len = decrypted[-1]
            decrypted = decrypted[:-pad_len]
            # Format: random(16) + msg_len(4) + msg + corp_id
            msg_len = socket.ntohl(struct.unpack("I", decrypted[16:20])[0])
            msg = decrypted[20:20 + msg_len].decode("utf-8")
            return msg
        except Exception as e:
            logger.error("Failed to decrypt echostr: %s", e)
            return ""

    def _decrypt_message(self, encrypted_xml: str) -> str:
        """Decrypt message body from <Encrypt> node."""
        try:
            root = ET.fromstring(encrypted_xml)
            encrypt_node = root.find("Encrypt")
            if encrypt_node is None or not encrypt_node.text:
                return ""

            aes_key = self._get_aes_key()
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
            decryptor = cipher.decryptor()
            encrypted = base64.b64decode(encrypt_node.text)
            decrypted = decryptor.update(encrypted) + decryptor.finalize()

            # Remove PKCS7 padding
            pad_len = decrypted[-1]
            decrypted = decrypted[:-pad_len]

            # Format: random(16) + msg_len(4) + msg + corp_id
            msg_len = socket.ntohl(struct.unpack("I", decrypted[16:20])[0])
            msg = decrypted[20:20 + msg_len].decode("utf-8")
            return msg
        except Exception as e:
            logger.error("Failed to decrypt WeChat Work message: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Access Token
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str:
        """Get or refresh WeChat Work access token."""
        global _access_token, _token_expires_at

        if _access_token and time.time() < _token_expires_at:
            return _access_token

        url = f"{_API_BASE}/gettoken"
        params = {"corpid": self._corp_id, "corpsecret": self._secret}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
                if result.get("errcode", -1) != 0:
                    logger.error("Failed to get WeChat Work token: %s", result.get("errmsg"))
                    return ""
                _access_token = result["access_token"]
                # Expire 5 minutes early for safety
                _token_expires_at = time.time() + result.get("expires_in", 7200) - 300
                return _access_token
        except Exception as e:
            logger.error("WeChat Work token request error: %s", e)
            return ""

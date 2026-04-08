"""WeChat Open Platform OAuth2 for website login (微信开放平台网站应用扫码登录)"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WeChatOAuthService:
    """
    WeChat OAuth2 Authorization Code Flow:
    1. Frontend redirects to WeChat QR code page
    2. User scans QR code with WeChat
    3. WeChat redirects back with authorization code
    4. Backend exchanges code for access_token + openid
    5. Backend gets user info (nickname, avatar)
    6. Backend creates/links user account, returns JWT
    """

    AUTH_URL = "https://open.weixin.qq.com/connect/qrconnect"
    TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
    USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"

    def __init__(self) -> None:
        self.app_id: str = settings.WECHAT_OPEN_APP_ID
        self.app_secret: str = settings.WECHAT_OPEN_APP_SECRET
        self.redirect_uri: str = settings.WECHAT_OPEN_REDIRECT_URI

    def is_configured(self) -> bool:
        """Check if WeChat Open Platform credentials are configured."""
        return bool(self.app_id and self.app_secret)

    def get_auth_url(self, state: str = "") -> str:
        """Generate WeChat QR code authorization URL.

        Frontend should redirect user to this URL or embed it in an iframe.

        Args:
            state: Random string for CSRF protection (should be stored in Redis)

        Returns:
            WeChat authorization URL
        """
        params = {
            "appid": self.app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "snsapi_login",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}#wechat_redirect"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access_token and openid.

        Args:
            code: Authorization code from WeChat callback

        Returns:
            {"access_token": "...", "openid": "...", "unionid": "...", "expires_in": 7200}

        Raises:
            ValueError: If WeChat returns an error
        """
        async with httpx.AsyncClient(proxy=None) as client:
            resp = await client.get(
                self.TOKEN_URL,
                params={
                    "appid": self.app_id,
                    "secret": self.app_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            data = resp.json()
            if "errcode" in data and data["errcode"] != 0:
                logger.error("WeChat OAuth exchange_code error: %s", data)
                raise ValueError(f"微信授权失败: {data.get('errmsg', 'unknown')}")
            return data

    async def get_user_info(self, access_token: str, openid: str) -> dict[str, Any]:
        """Get WeChat user profile.

        Args:
            access_token: Access token from exchange_code
            openid: User's openid from exchange_code

        Returns:
            {"openid": "...", "nickname": "...", "headimgurl": "...", "unionid": "..."}

        Raises:
            ValueError: If WeChat returns an error
        """
        async with httpx.AsyncClient(proxy=None) as client:
            resp = await client.get(
                self.USERINFO_URL,
                params={
                    "access_token": access_token,
                    "openid": openid,
                },
                timeout=10,
            )
            data = resp.json()
            if "errcode" in data and data["errcode"] != 0:
                logger.error("WeChat OAuth get_user_info error: %s", data)
                raise ValueError(f"获取微信用户信息失败: {data.get('errmsg', 'unknown')}")
            return data


wechat_oauth = WeChatOAuthService()

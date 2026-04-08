"""Alipay PC Payment (电脑网站支付) — 生产级实现。

使用 httpx + RSA2 (SHA256WithRSA) 签名直接对接支付宝 OpenAPI。
当商户凭证未配置时，所有方法返回 None / 抛出明确异常，
由上层 payment_service 决定回退到模拟支付。
"""

import base64
import json
import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15

from app.config import settings

logger = logging.getLogger(__name__)


def _load_private_key_from_str(key_str: str):
    """从 PEM 或裸 Base64 字符串加载 RSA 私钥。"""
    key_str = key_str.strip()
    if not key_str.startswith("-----BEGIN"):
        key_str = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            + key_str
            + "\n-----END RSA PRIVATE KEY-----"
        )
    return serialization.load_pem_private_key(key_str.encode("utf-8"), password=None)


def _load_public_key_from_str(key_str: str):
    """从 PEM 或裸 Base64 字符串加载 RSA 公钥。"""
    key_str = key_str.strip()
    if not key_str.startswith("-----BEGIN"):
        key_str = (
            "-----BEGIN PUBLIC KEY-----\n"
            + key_str
            + "\n-----END PUBLIC KEY-----"
        )
    return serialization.load_pem_public_key(key_str.encode("utf-8"))


class AlipayService:
    """支付宝电脑网站支付（alipay.trade.page.pay）。"""

    def __init__(self) -> None:
        self.app_id: str = settings.ALIPAY_APP_ID
        self._private_key_str: str = settings.ALIPAY_PRIVATE_KEY
        self._alipay_public_key_str: str = settings.ALIPAY_PUBLIC_KEY
        self.notify_url: str = settings.ALIPAY_NOTIFY_URL
        self.return_url: str = settings.ALIPAY_RETURN_URL
        # 生产环境网关
        self.gateway: str = "https://openapi.alipay.com/gateway.do"
        # 沙箱环境（调试时可切换）
        # self.gateway = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"

        self._private_key = None
        self._alipay_public_key = None

    # ------------------------------------------------------------------
    # 配置检测
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.app_id and self._private_key_str and self._alipay_public_key_str)

    # ------------------------------------------------------------------
    # 延迟加载密钥
    # ------------------------------------------------------------------

    def _get_private_key(self):
        if self._private_key is None:
            self._private_key = _load_private_key_from_str(self._private_key_str)
        return self._private_key

    def _get_alipay_public_key(self):
        if self._alipay_public_key is None:
            self._alipay_public_key = _load_public_key_from_str(self._alipay_public_key_str)
        return self._alipay_public_key

    # ------------------------------------------------------------------
    # RSA2 签名
    # ------------------------------------------------------------------

    def _sign(self, params: dict[str, str]) -> str:
        """对参数进行 RSA2 签名（SHA256WithRSA）。

        步骤：
        1. 过滤空值和 sign/sign_type
        2. 按 key ASCII 排序拼接为 key1=value1&key2=value2... 格式
        3. 使用应用私钥做 SHA256WithRSA 签名
        4. Base64 编码
        """
        # 过滤
        filtered = {
            k: v for k, v in params.items()
            if v and k not in ("sign", "sign_type")
        }
        # 排序拼接
        sign_content = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))

        private_key = self._get_private_key()
        signature = private_key.sign(sign_content.encode("utf-8"), PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")

    def _verify(self, params: dict[str, str], sign: str) -> bool:
        """验证支付宝回调签名。"""
        # 过滤
        filtered = {
            k: v for k, v in params.items()
            if v and k not in ("sign", "sign_type")
        }
        sign_content = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))

        public_key = self._get_alipay_public_key()
        try:
            public_key.verify(
                base64.b64decode(sign),
                sign_content.encode("utf-8"),
                PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 构建公共请求参数
    # ------------------------------------------------------------------

    def _build_common_params(self, method: str) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
        }

    # ------------------------------------------------------------------
    # 电脑网站支付（页面跳转）
    # ------------------------------------------------------------------

    async def create_page_pay(
        self, order_no: str, amount_yuan: str, subject: str
    ) -> str:
        """创建支付宝电脑网站支付链接。

        API: alipay.trade.page.pay
        返回: 完整支付 URL（前端跳转）
        """
        params = self._build_common_params("alipay.trade.page.pay")
        params["return_url"] = self.return_url
        params["notify_url"] = self.notify_url

        biz_content = {
            "out_trade_no": order_no,
            "total_amount": amount_yuan,
            "subject": subject,
            "product_code": "FAST_INSTANT_TRADE_PAY",
        }
        params["biz_content"] = json.dumps(biz_content, ensure_ascii=False)

        # 签名
        params["sign"] = self._sign(params)

        # 拼接成完整 URL
        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"{self.gateway}?{query_string}"

    # ------------------------------------------------------------------
    # 回调验签
    # ------------------------------------------------------------------

    async def verify_callback(self, params: dict[str, str]) -> dict:
        """验证支付宝异步回调签名。

        成功返回回调参数字典，失败抛出 ValueError。
        """
        sign = params.get("sign", "")
        if not sign:
            raise ValueError("回调缺少 sign 参数")

        if not self._verify(params, sign):
            raise ValueError("支付宝回调签名验证失败")

        return dict(params)

    # ------------------------------------------------------------------
    # 验证同步返回（GET 参数）
    # ------------------------------------------------------------------

    async def verify_return(self, params: dict[str, str]) -> dict:
        """验证支付宝同步返回签名。"""
        sign = params.get("sign", "")
        if not sign:
            raise ValueError("返回参数缺少 sign")
        if not self._verify(params, sign):
            raise ValueError("支付宝同步返回签名验证失败")
        return dict(params)

    # ------------------------------------------------------------------
    # 查询订单
    # ------------------------------------------------------------------

    async def query_order(self, order_no: str) -> dict:
        """查询订单状态。

        API: alipay.trade.query
        """
        params = self._build_common_params("alipay.trade.query")
        biz_content = {"out_trade_no": order_no}
        params["biz_content"] = json.dumps(biz_content)
        params["sign"] = self._sign(params)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(
                self.gateway,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            )

        result = resp.json()
        trade_response = result.get("alipay_trade_query_response", {})
        if trade_response.get("code") != "10000":
            logger.error("支付宝查询订单失败: %s", trade_response)
            raise RuntimeError(
                f"查询订单失败: {trade_response.get('sub_msg', trade_response.get('msg', '未知错误'))}"
            )
        return trade_response

    # ------------------------------------------------------------------
    # 退款
    # ------------------------------------------------------------------

    async def refund(self, order_no: str, amount_yuan: str, reason: str) -> dict:
        """申请退款。

        API: alipay.trade.refund
        """
        params = self._build_common_params("alipay.trade.refund")
        biz_content = {
            "out_trade_no": order_no,
            "refund_amount": amount_yuan,
            "refund_reason": reason,
        }
        params["biz_content"] = json.dumps(biz_content, ensure_ascii=False)
        params["sign"] = self._sign(params)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(
                self.gateway,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            )

        result = resp.json()
        refund_response = result.get("alipay_trade_refund_response", {})
        if refund_response.get("code") != "10000":
            logger.error("支付宝退款失败: %s", refund_response)
            raise RuntimeError(
                f"退款失败: {refund_response.get('sub_msg', refund_response.get('msg', '未知错误'))}"
            )
        return refund_response

    # ------------------------------------------------------------------
    # 关闭交易
    # ------------------------------------------------------------------

    async def close_order(self, order_no: str) -> dict:
        """关闭交易。

        API: alipay.trade.close
        """
        params = self._build_common_params("alipay.trade.close")
        biz_content = {"out_trade_no": order_no}
        params["biz_content"] = json.dumps(biz_content)
        params["sign"] = self._sign(params)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(
                self.gateway,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            )

        result = resp.json()
        close_response = result.get("alipay_trade_close_response", {})
        if close_response.get("code") != "10000":
            logger.error("支付宝关闭交易失败: %s", close_response)
            raise RuntimeError(
                f"关闭交易失败: {close_response.get('sub_msg', close_response.get('msg', '未知错误'))}"
            )
        return close_response


# 全局单例
alipay_service = AlipayService()

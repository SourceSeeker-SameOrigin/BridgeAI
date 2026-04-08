"""WeChat Pay V3 Native Payment (扫码支付) — 生产级实现。

使用 httpx + RSA-SHA256 签名直接对接微信支付 V3 API。
当商户凭证未配置时，所有方法返回 None / 抛出明确异常，
由上层 payment_service 决定回退到模拟支付。
"""

import base64
import hashlib
import json
import logging
import time
import uuid
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509 import load_pem_x509_certificate

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.mch.weixin.qq.com"


class WeChatPayService:
    """WeChat Pay V3 Native Payment (扫码支付)。"""

    def __init__(self) -> None:
        self.mch_id: str = settings.WECHAT_PAY_MCH_ID
        self.api_key_v3: str = settings.WECHAT_PAY_API_KEY_V3
        self.cert_serial_no: str = settings.WECHAT_PAY_CERT_SERIAL_NO
        self.private_key_path: str = settings.WECHAT_PAY_PRIVATE_KEY_PATH
        self.app_id: str = settings.WECHAT_PAY_APP_ID
        self.notify_url: str = settings.WECHAT_PAY_NOTIFY_URL
        self._private_key = None
        self._platform_certs: dict[str, object] = {}  # serial_no -> public_key

    # ------------------------------------------------------------------
    # 配置检测
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.mch_id and self.api_key_v3 and self.private_key_path and self.app_id)

    # ------------------------------------------------------------------
    # 加载商户私钥
    # ------------------------------------------------------------------

    def _load_private_key(self):
        """延迟加载商户 RSA 私钥。"""
        if self._private_key is not None:
            return self._private_key
        try:
            with open(self.private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(f.read(), password=None)
            return self._private_key
        except Exception as exc:
            logger.error("加载微信支付商户私钥失败: %s", exc)
            raise RuntimeError(f"无法加载微信支付商户私钥: {exc}") from exc

    # ------------------------------------------------------------------
    # V3 签名生成
    # ------------------------------------------------------------------

    def _build_auth_header(self, method: str, url_path: str, body: str = "") -> str:
        """构造 Authorization 头（WECHATPAY2-SHA256-RSA2048 签名）。

        签名串格式：
            HTTP请求方法\\n
            URL（不含域名）\\n
            请求时间戳\\n
            请求随机串\\n
            请求报文主体（GET 为空）\\n
        """
        timestamp = str(int(time.time()))
        nonce_str = uuid.uuid4().hex
        sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"

        private_key = self._load_private_key()
        signature = private_key.sign(sign_str.encode("utf-8"), PKCS1v15(), hashes.SHA256())
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",'
            f'nonce_str="{nonce_str}",'
            f'signature="{signature_b64}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self.cert_serial_no}"'
        )

    def _build_headers(self, method: str, url_path: str, body: str = "") -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": self._build_auth_header(method, url_path, body),
        }

    # ------------------------------------------------------------------
    # 创建 Native 支付订单
    # ------------------------------------------------------------------

    async def create_native_order(
        self, order_no: str, amount_cents: int, description: str
    ) -> dict:
        """创建微信支付 Native 订单，返回 code_url（用于生成二维码）。

        API: POST /v3/pay/transactions/native
        """
        url_path = "/v3/pay/transactions/native"
        payload = {
            "appid": self.app_id,
            "mchid": self.mch_id,
            "description": description,
            "out_trade_no": order_no,
            "notify_url": self.notify_url,
            "amount": {
                "total": amount_cents,
                "currency": "CNY",
            },
        }
        body = json.dumps(payload, ensure_ascii=False)
        headers = self._build_headers("POST", url_path, body)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(f"{_BASE_URL}{url_path}", content=body, headers=headers)

        if resp.status_code != 200:
            logger.error("微信支付下单失败: status=%s body=%s", resp.status_code, resp.text)
            raise RuntimeError(f"微信支付下单失败: {resp.status_code} {resp.text}")

        data = resp.json()
        return {"code_url": data["code_url"], "order_no": order_no}

    # ------------------------------------------------------------------
    # 回调验签 + 解密
    # ------------------------------------------------------------------

    async def verify_callback(self, headers: dict, body: str) -> dict:
        """验证微信支付回调签名并解密通知数据。

        headers 需含: Wechatpay-Timestamp, Wechatpay-Nonce, Wechatpay-Signature, Wechatpay-Serial
        """
        timestamp = headers.get("Wechatpay-Timestamp", "")
        nonce = headers.get("Wechatpay-Nonce", "")
        signature_b64 = headers.get("Wechatpay-Signature", "")
        serial_no = headers.get("Wechatpay-Serial", "")

        if not all([timestamp, nonce, signature_b64, serial_no]):
            raise ValueError("回调缺少必要的签名头信息")

        # 构造验签串
        sign_str = f"{timestamp}\n{nonce}\n{body}\n"

        # 验证签名（需要平台证书公钥）
        platform_pub_key = self._platform_certs.get(serial_no)
        if platform_pub_key is None:
            # 尝试下载平台证书
            await self._fetch_platform_certificates()
            platform_pub_key = self._platform_certs.get(serial_no)
            if platform_pub_key is None:
                raise ValueError(f"未找到序列号 {serial_no} 对应的平台证书")

        signature = base64.b64decode(signature_b64)
        try:
            platform_pub_key.verify(signature, sign_str.encode("utf-8"), PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise ValueError(f"回调签名验证失败: {exc}") from exc

        # 解密通知数据
        notification = json.loads(body)
        resource = notification.get("resource", {})
        return self._decrypt_resource(resource)

    def _decrypt_resource(self, resource: dict) -> dict:
        """使用 AEAD_AES_256_GCM 解密回调通知中的 resource。"""
        algorithm = resource.get("algorithm", "")
        if algorithm != "AEAD_AES_256_GCM":
            raise ValueError(f"不支持的加密算法: {algorithm}")

        nonce = resource["nonce"].encode("utf-8")
        ciphertext = base64.b64decode(resource["ciphertext"])
        associated_data = resource.get("associated_data", "").encode("utf-8")

        key = self.api_key_v3.encode("utf-8")
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))

    # ------------------------------------------------------------------
    # 下载平台证书
    # ------------------------------------------------------------------

    async def _fetch_platform_certificates(self) -> None:
        """下载微信支付平台证书并缓存公钥。

        API: GET /v3/certificates
        """
        url_path = "/v3/certificates"
        headers = self._build_headers("GET", url_path)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.get(f"{_BASE_URL}{url_path}", headers=headers)

        if resp.status_code != 200:
            logger.error("获取平台证书失败: %s %s", resp.status_code, resp.text)
            return

        data = resp.json()
        for cert_item in data.get("data", []):
            serial = cert_item["serial_no"]
            encrypt_cert = cert_item["encrypt_certificate"]
            cert_pem = self._decrypt_resource(encrypt_cert)
            # cert_pem 解密后是 PEM 格式的证书字符串
            if isinstance(cert_pem, str):
                cert_bytes = cert_pem.encode("utf-8")
            else:
                cert_bytes = cert_pem
            x509_cert = load_pem_x509_certificate(cert_bytes)
            self._platform_certs[serial] = x509_cert.public_key()
            logger.info("已缓存平台证书: serial=%s", serial)

    # ------------------------------------------------------------------
    # 查询订单
    # ------------------------------------------------------------------

    async def query_order(self, order_no: str) -> dict:
        """查询订单状态。

        API: GET /v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={mchid}
        """
        url_path = f"/v3/pay/transactions/out-trade-no/{order_no}?mchid={self.mch_id}"
        headers = self._build_headers("GET", url_path)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.get(f"{_BASE_URL}{url_path}", headers=headers)

        if resp.status_code != 200:
            logger.error("查询订单失败: %s %s", resp.status_code, resp.text)
            raise RuntimeError(f"查询订单失败: {resp.status_code} {resp.text}")

        return resp.json()

    # ------------------------------------------------------------------
    # 关闭订单
    # ------------------------------------------------------------------

    async def close_order(self, order_no: str) -> None:
        """关闭未支付订单。

        API: POST /v3/pay/transactions/out-trade-no/{out_trade_no}/close
        """
        url_path = f"/v3/pay/transactions/out-trade-no/{order_no}/close"
        payload = {"mchid": self.mch_id}
        body = json.dumps(payload)
        headers = self._build_headers("POST", url_path, body)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(f"{_BASE_URL}{url_path}", content=body, headers=headers)

        if resp.status_code not in (200, 204):
            logger.error("关闭订单失败: %s %s", resp.status_code, resp.text)
            raise RuntimeError(f"关闭订单失败: {resp.status_code} {resp.text}")

    # ------------------------------------------------------------------
    # 退款
    # ------------------------------------------------------------------

    async def refund(
        self, order_no: str, refund_no: str, amount_cents: int, total_cents: int, reason: str
    ) -> dict:
        """申请退款。

        API: POST /v3/refund/domestic/refunds
        """
        url_path = "/v3/refund/domestic/refunds"
        payload = {
            "out_trade_no": order_no,
            "out_refund_no": refund_no,
            "reason": reason,
            "notify_url": self.notify_url,
            "amount": {
                "refund": amount_cents,
                "total": total_cents,
                "currency": "CNY",
            },
        }
        body = json.dumps(payload, ensure_ascii=False)
        headers = self._build_headers("POST", url_path, body)

        async with httpx.AsyncClient(proxy=None, timeout=10.0) as client:
            resp = await client.post(f"{_BASE_URL}{url_path}", content=body, headers=headers)

        if resp.status_code not in (200, 201):
            logger.error("退款申请失败: %s %s", resp.status_code, resp.text)
            raise RuntimeError(f"退款申请失败: {resp.status_code} {resp.text}")

        return resp.json()


# 全局单例
wechat_pay_service = WeChatPayService()

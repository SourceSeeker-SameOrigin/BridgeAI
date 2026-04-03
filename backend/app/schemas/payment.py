"""Payment schemas."""

from typing import Optional

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    plan: str
    months: int = 1
    payment_method: str = "wechat"  # wechat / alipay


class PayOrderRequest(BaseModel):
    payment_method: str = "wechat"  # wechat / alipay


class UpgradePlanRequest(BaseModel):
    plan: str


class OrderResponse(BaseModel):
    id: str
    order_no: str
    plan: str
    months: int
    amount: float
    currency: str
    status: str
    payment_method: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class PaymentResult(BaseModel):
    order_id: str
    order_no: str
    status: str
    message: str
    payment_url: Optional[str] = None   # 支付宝跳转URL
    code_url: Optional[str] = None      # 微信支付二维码链接
    simulated: bool = False             # 是否为模拟支付（凭证未配置时）

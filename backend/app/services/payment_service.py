"""Payment Service — 支付订单与套餐升级。

集成微信支付（Native 扫码支付）和支付宝（电脑网站支付）。
当商户凭证未配置时，自动回退为模拟支付流程。
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentOrder
from app.models.user import Tenant
from app.schemas.payment import OrderResponse, PaymentResult
from app.services.alipay_pay import alipay_service
from app.services.wechat_pay import wechat_pay_service

logger = logging.getLogger(__name__)

# 套餐价格配置（元/月）
PLAN_PRICES: dict[str, float] = {
    "free": 0.0,
    "pro": 99.0,
    "enterprise": 499.0,
}


def _generate_order_no() -> str:
    """生成订单号：时间戳 + 随机后缀。"""
    now = datetime.now(timezone.utc)
    return f"ORD{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _order_to_response(order: PaymentOrder) -> OrderResponse:
    return OrderResponse(
        id=str(order.id),
        order_no=order.order_no,
        plan=order.plan,
        months=order.months,
        amount=order.amount,
        currency=order.currency,
        status=order.status,
        payment_method=order.payment_method,
        paid_at=order.paid_at.isoformat() if order.paid_at else None,
        created_at=order.created_at.isoformat() if order.created_at else "",
    )


class PaymentService:
    """支付服务：创建订单、对接真实支付通道、升级套餐。"""

    async def create_order(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        plan: str,
        months: int,
        payment_method: str = "wechat",
    ) -> PaymentResult:
        """创建支付订单并发起支付。

        根据 payment_method 调用对应支付通道：
        - wechat: 返回 code_url（前端生成二维码）
        - alipay: 返回 payment_url（前端跳转）
        - 如果对应通道未配置，回退到模拟支付
        """
        if plan not in PLAN_PRICES:
            raise ValueError(f"无效套餐: {plan}")
        if months < 1 or months > 36:
            raise ValueError("订购月数应在 1-36 之间")

        price = PLAN_PRICES[plan]
        amount = price * months

        order = PaymentOrder(
            tenant_id=uuid.UUID(tenant_id),
            user_id=uuid.UUID(user_id),
            order_no=_generate_order_no(),
            plan=plan,
            months=months,
            amount=amount,
            currency="CNY",
            status="pending",
            payment_method=payment_method,
        )
        db.add(order)
        await db.flush()
        await db.refresh(order)

        logger.info(
            "Payment order created: %s, plan=%s, amount=%.2f, method=%s",
            order.order_no, plan, amount, payment_method,
        )

        # 尝试调用真实支付通道
        return await self._initiate_payment(order, payment_method)

    async def _initiate_payment(
        self, order: PaymentOrder, payment_method: str
    ) -> PaymentResult:
        """根据支付方式发起真实支付或模拟支付。"""
        order_id = str(order.id)
        order_no = order.order_no
        amount = order.amount
        plan = order.plan
        description = f"BridgeAI {plan} 套餐 - {order.months}个月"

        # 微信支付
        if payment_method == "wechat" and wechat_pay_service.is_configured():
            try:
                amount_cents = int(amount * 100)  # 元 -> 分
                result = await wechat_pay_service.create_native_order(
                    order_no=order_no,
                    amount_cents=amount_cents,
                    description=description,
                )
                return PaymentResult(
                    order_id=order_id,
                    order_no=order_no,
                    status="pending",
                    message="请使用微信扫码支付",
                    code_url=result["code_url"],
                    simulated=False,
                )
            except Exception as exc:
                logger.error("微信支付下单失败，回退模拟支付: %s", exc)

        # 支付宝
        if payment_method == "alipay" and alipay_service.is_configured():
            try:
                amount_yuan = f"{amount:.2f}"
                payment_url = await alipay_service.create_page_pay(
                    order_no=order_no,
                    amount_yuan=amount_yuan,
                    subject=description,
                )
                return PaymentResult(
                    order_id=order_id,
                    order_no=order_no,
                    status="pending",
                    message="请跳转支付宝完成支付",
                    payment_url=payment_url,
                    simulated=False,
                )
            except Exception as exc:
                logger.error("支付宝下单失败，回退模拟支付: %s", exc)

        # 回退：模拟支付（凭证未配置或调用失败）
        logger.warning(
            "支付通道 %s 未配置或不可用，使用模拟支付: order=%s",
            payment_method, order_no,
        )
        return PaymentResult(
            order_id=order_id,
            order_no=order_no,
            status="pending",
            message=f"支付通道 ({payment_method}) 未配置，当前为模拟支付模式。"
                    f"请调用 POST /orders/{order_id}/pay 模拟完成支付。",
            simulated=True,
        )

    async def process_payment(
        self,
        db: AsyncSession,
        order_id: str,
        payment_method: str,
        tenant_id: str,
    ) -> PaymentResult:
        """模拟支付处理（兼容原有流程）。

        生产环境下此接口仅用于测试/管理员手动确认，
        真实支付通过回调接口完成。
        """
        oid = uuid.UUID(order_id)
        result = await db.execute(
            select(PaymentOrder).where(
                PaymentOrder.id == oid,
                PaymentOrder.tenant_id == uuid.UUID(tenant_id),
            )
        )
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError("订单不存在")
        if order.status == "paid":
            return PaymentResult(
                order_id=str(order.id),
                order_no=order.order_no,
                status="paid",
                message="订单已支付",
                simulated=False,
            )
        if order.status != "pending":
            raise ValueError(f"订单状态异常: {order.status}")

        # --- 模拟支付成功 ---
        now = datetime.now(timezone.utc)
        order.status = "paid"
        order.payment_method = payment_method
        order.paid_at = now
        await db.flush()

        # 支付成功后自动升级套餐
        await self._upgrade_tenant_plan(db, str(order.tenant_id), order.plan)

        logger.info("Payment completed (simulated): %s via %s", order.order_no, payment_method)
        return PaymentResult(
            order_id=str(order.id),
            order_no=order.order_no,
            status="paid",
            message="支付成功，套餐已升级（模拟支付）",
            simulated=True,
        )

    async def handle_payment_success(
        self,
        db: AsyncSession,
        order_no: str,
        payment_method: str,
        transaction_id: Optional[str] = None,
    ) -> bool:
        """处理支付成功回调（微信/支付宝共用）。

        返回 True 表示处理成功，False 表示订单不存在或已处理。
        """
        result = await db.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        order = result.scalar_one_or_none()

        if order is None:
            logger.warning("回调订单不存在: %s", order_no)
            return False

        if order.status == "paid":
            logger.info("订单已处理，跳过: %s", order_no)
            return True  # 幂等处理

        if order.status != "pending":
            logger.warning("订单状态异常，无法处理回调: %s status=%s", order_no, order.status)
            return False

        now = datetime.now(timezone.utc)
        order.status = "paid"
        order.payment_method = payment_method
        order.paid_at = now
        if transaction_id:
            order.metadata_ = {**(order.metadata_ or {}), "transaction_id": transaction_id}
        await db.flush()

        # 升级套餐
        await self._upgrade_tenant_plan(db, str(order.tenant_id), order.plan)

        logger.info(
            "Payment callback success: order=%s method=%s txn=%s",
            order_no, payment_method, transaction_id,
        )
        return True

    async def upgrade_plan(
        self,
        db: AsyncSession,
        tenant_id: str,
        new_plan: str,
    ) -> None:
        """直接升级套餐（测试/管理员用途）。"""
        if new_plan not in PLAN_PRICES:
            raise ValueError(f"无效套餐: {new_plan}")
        await self._upgrade_tenant_plan(db, tenant_id, new_plan)
        logger.info("Tenant %s plan upgraded to %s (direct)", tenant_id, new_plan)

    async def get_orders(
        self,
        db: AsyncSession,
        tenant_id: str,
    ) -> list[OrderResponse]:
        """获取租户的支付订单历史。"""
        tid = uuid.UUID(tenant_id)
        result = await db.execute(
            select(PaymentOrder)
            .where(PaymentOrder.tenant_id == tid)
            .order_by(PaymentOrder.created_at.desc())
            .limit(100)
        )
        orders = result.scalars().all()
        return [_order_to_response(o) for o in orders]

    async def get_order_by_no(
        self,
        db: AsyncSession,
        order_no: str,
    ) -> Optional[PaymentOrder]:
        """根据订单号查询订单。"""
        result = await db.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        return result.scalar_one_or_none()

    async def _upgrade_tenant_plan(
        self,
        db: AsyncSession,
        tenant_id: str,
        new_plan: str,
    ) -> None:
        """更新租户套餐。"""
        tid = uuid.UUID(tenant_id)
        await db.execute(
            update(Tenant).where(Tenant.id == tid).values(plan=new_plan)
        )
        await db.flush()


# Global singleton
payment_service = PaymentService()

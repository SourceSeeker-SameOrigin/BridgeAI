"""Payment API — 订单创建、支付、回调、套餐升级。"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.payment import (
    CreateOrderRequest,
    OrderResponse,
    PaymentResult,
    PayOrderRequest,
    UpgradePlanRequest,
)
from app.services.alipay_pay import alipay_service
from app.services.payment_service import payment_service
from app.services.wechat_pay import wechat_pay_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.post("/orders", response_model=ApiResponse[PaymentResult])
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Create a payment order and initiate payment.

    Returns payment URL (alipay) or QR code URL (wechat).
    Falls back to simulated payment when credentials are not configured.
    """
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        raise BadRequestException(message="用户未关联租户")

    try:
        result = await payment_service.create_order(
            db=db,
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            plan=request.plan,
            months=request.months,
            payment_method=request.payment_method,
        )
        await db.commit()
        return ApiResponse.success(data=result)
    except ValueError as e:
        raise BadRequestException(message=str(e))


@router.post("/orders/{order_id}/pay", response_model=ApiResponse[PaymentResult])
async def pay_order(
    order_id: str,
    request: PayOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Simulate payment for an existing order (test/admin usage)."""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        raise BadRequestException(message="用户未关联租户")

    try:
        result = await payment_service.process_payment(
            db=db,
            order_id=order_id,
            payment_method=request.payment_method,
            tenant_id=tenant_id,
        )
        await db.commit()
        return ApiResponse.success(data=result)
    except ValueError as e:
        raise BadRequestException(message=str(e))


@router.get("/orders", response_model=ApiResponse[list[OrderResponse]])
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List payment orders for the current tenant."""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        raise BadRequestException(message="用户未关联租户")

    orders = await payment_service.get_orders(db=db, tenant_id=tenant_id)
    return ApiResponse.success(data=orders)


@router.post("/upgrade", response_model=ApiResponse)
async def upgrade_plan(
    request: UpgradePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Directly upgrade tenant plan (admin/test usage)."""
    tenant_id = str(current_user.tenant_id) if current_user.tenant_id else None
    if not tenant_id:
        raise BadRequestException(message="用户未关联租户")

    try:
        await payment_service.upgrade_plan(db=db, tenant_id=tenant_id, new_plan=request.plan)
        await db.commit()
        return ApiResponse.success(message=f"套餐已升级为 {request.plan}")
    except ValueError as e:
        raise BadRequestException(message=str(e))


# ======================================================================
# 支付回调端点（不需要用户认证）
# ======================================================================


@router.post("/callback/wechat")
async def wechat_pay_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """微信支付异步回调通知。

    微信支付服务器会 POST JSON 到此端点，需要验签 + 解密后处理。
    返回 {"code": "SUCCESS"} 表示处理成功。
    """
    if not wechat_pay_service.is_configured():
        logger.warning("收到微信支付回调但凭证未配置")
        return {"code": "FAIL", "message": "payment not configured"}

    try:
        body = (await request.body()).decode("utf-8")
        callback_headers = {
            "Wechatpay-Timestamp": request.headers.get("Wechatpay-Timestamp", ""),
            "Wechatpay-Nonce": request.headers.get("Wechatpay-Nonce", ""),
            "Wechatpay-Signature": request.headers.get("Wechatpay-Signature", ""),
            "Wechatpay-Serial": request.headers.get("Wechatpay-Serial", ""),
        }

        # 验签并解密
        notification = await wechat_pay_service.verify_callback(callback_headers, body)
        logger.info("微信支付回调验签成功: %s", notification.get("out_trade_no", ""))

        trade_state = notification.get("trade_state", "")
        order_no = notification.get("out_trade_no", "")
        transaction_id = notification.get("transaction_id", "")

        if trade_state == "SUCCESS":
            success = await payment_service.handle_payment_success(
                db=db,
                order_no=order_no,
                payment_method="wechat",
                transaction_id=transaction_id,
            )
            await db.commit()
            if success:
                return {"code": "SUCCESS", "message": "OK"}

        return {"code": "SUCCESS", "message": "OK"}

    except ValueError as exc:
        logger.error("微信支付回调验签失败: %s", exc)
        return {"code": "FAIL", "message": str(exc)}
    except Exception as exc:
        logger.error("微信支付回调处理异常: %s", exc, exc_info=True)
        return {"code": "FAIL", "message": "internal error"}


@router.post("/callback/alipay")
async def alipay_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """支付宝异步回调通知。

    支付宝服务器会 POST form-encoded 到此端点，需要验签后处理。
    返回纯文本 "success" 表示处理成功，"fail" 表示失败。
    """
    if not alipay_service.is_configured():
        logger.warning("收到支付宝回调但凭证未配置")
        return PlainTextResponse("fail")

    try:
        form_data = await request.form()
        params = {k: v for k, v in form_data.items() if isinstance(v, str)}

        # 验签
        verified = await alipay_service.verify_callback(params)
        logger.info("支付宝回调验签成功: %s", verified.get("out_trade_no", ""))

        trade_status = verified.get("trade_status", "")
        order_no = verified.get("out_trade_no", "")
        trade_no = verified.get("trade_no", "")  # 支付宝交易号

        if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            success = await payment_service.handle_payment_success(
                db=db,
                order_no=order_no,
                payment_method="alipay",
                transaction_id=trade_no,
            )
            await db.commit()
            if success:
                return PlainTextResponse("success")

        return PlainTextResponse("success")

    except ValueError as exc:
        logger.error("支付宝回调验签失败: %s", exc)
        return PlainTextResponse("fail")
    except Exception as exc:
        logger.error("支付宝回调处理异常: %s", exc, exc_info=True)
        return PlainTextResponse("fail")


@router.get("/return/alipay", response_model=ApiResponse)
async def alipay_return(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """支付宝同步返回（用户支付后浏览器跳转回来）。

    此端点验证签名后返回支付状态，前端据此展示结果页。
    """
    if not alipay_service.is_configured():
        return ApiResponse.success(message="支付通道未配置（模拟模式）")

    try:
        params = dict(request.query_params)
        verified = await alipay_service.verify_return(params)

        order_no = verified.get("out_trade_no", "")

        # 查询订单状态
        order = await payment_service.get_order_by_no(db=db, order_no=order_no)
        if order is None:
            return ApiResponse.error(code=404, message="订单不存在")

        return ApiResponse.success(
            data={
                "order_no": order.order_no,
                "status": order.status,
                "plan": order.plan,
                "amount": order.amount,
            },
            message="支付完成" if order.status == "paid" else "支付处理中",
        )

    except ValueError as exc:
        logger.error("支付宝同步返回验签失败: %s", exc)
        return ApiResponse.error(code=400, message=f"签名验证失败: {exc}")
    except Exception as exc:
        logger.error("支付宝同步返回处理异常: %s", exc, exc_info=True)
        return ApiResponse.error(code=500, message="处理异常")

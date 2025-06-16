import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.order_service import order_service
from app.services.payment_service import alipay_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/payment/alipay/notify", summary="支付宝异步通知回调", include_in_schema=False)
async def alipay_notify(request: Request, db: AsyncSession = Depends(get_db)):
    """
    处理支付宝发送的异步通知
    这是服务器到服务器的通信，不暴露在API文档中
    """
    # 1. 解析支付宝发送的 Form-encoded 数据
    try:
        notification_data = dict(await request.form())
        logger.info(f"接收到支付宝异步通知: {notification_data}")
    except Exception as e:
        logger.error(f"解析支付宝通知数据失败: {e}", exc_info=True)
        return Response(content="failure", media_type="text/plain")

    # 2. 调用支付服务进行验签 (传入副本以防原始数据在验签过程中被修改)
    is_verified = alipay_service.verify_notification(notification_data.copy())

    if not is_verified:
        logger.warning(f"支付宝通知验签失败. 数据: {notification_data}")
        return Response(content="failure", media_type="text/plain")

    # 3. 验签成功，处理业务逻辑
    # 支付宝文档规定，需要验证 trade_status 是否为 TRADE_SUCCESS 或 TRADE_FINISHED
    trade_status = notification_data.get('trade_status')
    if trade_status not in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
        logger.info(f"忽略非成功状态的支付宝通知: {trade_status}")
        # 对于非成功状态的通知，也应返回 "success"，表示已成功接收，无需支付宝重发
        return Response(content="success", media_type="text/plain")

    try:
        # 从通知中提取业务所需数据
        order_sn = notification_data.get('out_trade_no')
        trade_no = notification_data.get('trade_no')
        total_amount_str = notification_data.get('total_amount')
        gmt_payment_str = notification_data.get('gmt_payment')

        if not all([order_sn, trade_no, total_amount_str, gmt_payment_str]):
            logger.error(f"支付宝通知中缺少必要字段. 数据: {notification_data}")
            return Response(content="failure", media_type="text/plain")

        total_amount = float(total_amount_str)
        payment_time = datetime.strptime(gmt_payment_str, '%Y-%m-%d %H:%M:%S')

        # 4. 调用订单服务处理支付结果
        success = await order_service.process_payment_notification(
            db=db,
            order_sn=order_sn,
            trade_no=trade_no,
            paid_at=payment_time,
            total_amount=total_amount
        )

        if success:
            logger.info(f"成功处理订单 {order_sn} 的支付通知。")
            return Response(content="success", media_type="text/plain")
        else:
            logger.error(f"处理订单 {order_sn} 的支付通知时业务逻辑失败。")
            # 业务失败但通知已收到，仍返回success避免重发，问题留由内部排查
            return Response(content="success", media_type="text/plain")

    except Exception as e:
        order_sn = notification_data.get('out_trade_no', 'N/A')
        logger.error(f"处理订单 {order_sn} 的支付通知时发生意外错误: {e}", exc_info=True)
        return Response(content="failure", media_type="text/plain")

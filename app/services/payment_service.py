import json
import logging

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.util.SignatureUtils import verify_with_rsa

from app.core.config import settings

logger = logging.getLogger(__name__)


class AlipayService:
    def __init__(self):
        """初始化支付宝客户端，使用 DefaultAlipayClient"""
        alipay_client_config = AlipayClientConfig()
        alipay_client_config.server_url = settings.ALIPAY_GATEWAY_URL
        alipay_client_config.app_id = settings.ALIPAY_APP_ID
        alipay_client_config.app_private_key = settings.ALIPAY_APP_PRIVATE_KEY
        alipay_client_config.alipay_public_key = settings.ALIPAY_PUBLIC_KEY

        if settings.ALIPAY_DEBUG:
            logger.info(f"Alipay SDK initialized in SANDBOX mode with gateway: {alipay_client_config.server_url}")
        else:
            logger.info(f"Alipay SDK initialized in PRODUCTION mode with gateway: {alipay_client_config.server_url}")

        self.client = DefaultAlipayClient(alipay_client_config=alipay_client_config, logger=logger)
        # 保存支付宝公钥字符串，用于手动验签
        self.alipay_public_key_string = settings.ALIPAY_PUBLIC_KEY

    def create_pc_payment_url(self, order_sn: str, total_amount: float, subject: str) -> str:
        """
        生成电脑网站支付的URL
        :param order_sn: 商户订单号
        :param total_amount: 订单总金额
        :param subject: 订单标题
        :return: 支付宝支付页面的URL
        """
        request = AlipayTradePagePayRequest()
        request.notify_url = settings.ALIPAY_NOTIFY_URL
        request.return_url = settings.ALIPAY_RETURN_URL

        biz_content = {
            "out_trade_no": order_sn,
            "total_amount": f"{total_amount:.2f}",
            "subject": subject,
            "product_code": "FAST_INSTANT_TRADE_PAY"
        }
        request.biz_content = biz_content

        try:
            payment_url = self.client.page_execute(request, http_method="GET")
            logger.info(f"Generated Alipay payment URL for order {order_sn}: {payment_url}")
            return payment_url
        except Exception as e:
            logger.error(f"Error generating Alipay payment URL for order {order_sn}: {e}", exc_info=True)
            raise Exception(f"生成支付宝支付链接失败: {e}")

    def verify_notification(self, notification_data: dict) -> bool:
        """
        验证支付宝异步通知的签名
        """
        if not notification_data:
            logger.warning("支付宝验签失败：未收到任何通知数据。")
            return False

        sign = notification_data.pop('sign', None)
        # 支付宝验签时，sign_type 字段不参与签名，移除
        notification_data.pop('sign_type', None)

        # 增加 isinstance 判断，让静态分析工具能够确认 sign 的类型，从而消除警告
        if not isinstance(sign, str) or not sign:
            logger.warning("支付宝验签失败：通知数据中未找到'sign'或'sign'格式不正确。")
            return False

        # 1. 对参数进行排序
        sorted_items = sorted(notification_data.items())

        # 2. 拼接成 key=value&key2=value2 格式的字符串
        message_parts = []
        for key, value in sorted_items:
            # 支付宝官方文档规定，值为空的参数不参与签名
            if key and value is not None and str(value) != '':
                val_str = str(value)
                # 尝试对JSON格式的字符串进行标准化，消除格式差异
                if val_str.startswith('[') or val_str.startswith('{'):
                    try:
                        # 解析后再序列化，可以去除多余的空格等，确保格式统一
                        parsed_json = json.loads(val_str)
                        val_str = json.dumps(parsed_json, separators=(',', ':'))
                    except json.JSONDecodeError:
                        # 如果不是合法的JSON，则使用原始字符串
                        pass
                message_parts.append(f"{key}={val_str}")
        message = "&".join(message_parts)

        # 使用官方SDK的工具函数进行验签
        logger.info(f"Alipay verification: String to be signed for SDK verification: '{message}'")

        try:
            # 调用官方SDK的验签函数
            is_verified = verify_with_rsa(
                public_key=self.alipay_public_key_string,
                message=message.encode('utf-8'),
                sign=sign
            )

            if is_verified:
                logger.info("支付宝通知验签成功 (SDK util)。")
            else:
                logger.warning(f"支付宝通知验签失败 (SDK util)。数据: {notification_data}, 签名: {sign}")
            return is_verified
        except Exception as e:
            logger.error(f"支付宝验签时发生意外错误 (SDK util): {e}", exc_info=True)
            return False


# 创建一个全局服务实例
alipay_service = AlipayService()

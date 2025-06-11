import os
from pathlib import Path

import aiosmtplib
from email.message import EmailMessage
from jinja2 import Template
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", SMTP_USER)
DEFAULT_TO = [addr.strip() for addr in os.getenv("ALERT_EMAIL_TO", "").split(",") if addr]

# 简单 Jinja2 模板，暂不替换为文件
HTML_TEMPLATE = """
<h3>⚠️ 低库存预警</h3>
<ul>
  <li>库存项 ID: {{ inventory_item_id }}</li>
  <li>当前库存: {{ quantity }}</li>
  <li>可用库存: {{ available_quantity | default('N/A') }}</li>
  <li>预警阈值: {{ alert_threshold }}</li>
</ul>
<p>请及时补货或调整库存策略。</p>
"""


async def send_low_stock_email(alert: dict, to: list[str] | None = None) -> None:
    to = to or DEFAULT_TO
    if not to:
        return  # 没配置收件人直接忽略

    subject = f"⚠️ 低库存预警 - 库存项 {alert.get('inventory_item_id')}"
    html_body = Template(HTML_TEMPLATE).render(**alert)

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content("请使用支持 HTML 的客户端查看此邮件。")
    msg.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASS,
        use_tls=SMTP_PORT == 465,  # 465 常用 SSL
        start_tls=SMTP_PORT in (587, 25),  # 587/25 STARTTLS
        timeout=10.0  # 添加超时
    )

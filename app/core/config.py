from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""

    # API配置
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:qqabc20040520@localhost:3306/for_ecommerce_backend"

    # Elasticsearch配置
    ELASTICSEARCH_HOSTS: list = ["http://localhost:9200"]
    ELASTICSEARCH_USERNAME: str = ""  # 如果有设置认证，则填写
    ELASTICSEARCH_PASSWORD: str = ""  # 如果有设置认证，则填写
    ELASTICSEARCH_PRODUCT_INDEX: str = "products"  # 商品索引名称
    ELASTICSEARCH_CA_CERTS: str = ""  # 如果启用了SSL/TLS，提供CA证书路径
    ELASTICSEARCH_VERIFY_CERTS: bool = False  # 是否验证SSL证书

    # 支付宝支付配置
    ALIPAY_APP_ID: str = "9021000149666167"  # 支付宝应用ID
    SELLER_ID: str = "2088721070380440"  # 沙箱环境卖家ID
    BUYER_ID: str = "2088722070428710"  # 沙箱环境买家ID
    ALIPAY_GATEWAY_URL: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"  # 沙箱环境支付网关
    # 应用私钥
    ALIPAY_APP_PRIVATE_KEY: str = "MIIEpQIBAAKCAQEArowV6nRl+fuyklbwcHO5LlveaTgFflGVqCMMb4MxHIOHSt+Z/0/Mz8oxH+H3s1LhsjikKqnkoiYpdumYf5IRrhY5aBJ+BsXHvjWYRDfQn3m4v0v3s86CEQOyi4x8vwRapOURo6uIA2hTmO9+pcxn9Wzn89zv0tHaKLipqn96Lm1eKE151zZAHR9aFrtHWbYgas23mHEdZkP31/zOLo1c3VxMwBPWFvtcu8xlpPe26/hhWRG8nmkn4HoVsCz/DpgRSpb7osHP53+c8iEHrJOgBrfPYRMrnL3PBlZzrF/n9rh/vZ6y0fId9hEmUtRrzoxs1JAIflp6N9tSfyvBDoU4oQIDAQABAoIBADtIgw0NmbEtJrqDYsie1W+EbmcISv1bUlw4AzpAscaAecwZY+GORf7xKnwssIesh9GTYVbIO0pDcePcdRonD3A0Ri0t0rYUKMJWy6+n0WjI29HFSI0+f3it689v2NK79Nl6n+IaGWkm3vXbqgVABrMZ2TI/gQj2k4UvKxkokOQBWohMf0pDnsrHvzHrwPYue9lc0jepYSXdP94nklVhMGa8jzlIVnsYQBKt+bdFfNHntxPuipqgowPNtFVwcLCjKLO8lOmk0Zs+5v5h+7oQr+GeOLaaqsEjkzGtBx3n3JFOJa+IWrmt5YaR7u91VQqzMQXtujxfrFVQ0IjC6UTBG00CgYEA8f2zHrARJjlQB26YHdPMwSYObZGRUU2vbiTJf+ypame1r5ygJDBmHbJwYMfPkdPVP6re9v2BKH8aFmGTfGv1UyKBYSTcO4aHZGgI9PyzpTetVuSHLoGQRo03MTmt4HpR3yY1xCfdfqSpddxNQEaFVPTykGC8TKVUTEUz2fvhVicCgYEAuKbe3EzM1KBfnUGA2bUGpEmgnvS4BIFlPMzGBJUvl2s1Wk7laF68ltAPovQNisgD7fzYp9+kKFGZUQf/cR5Rn2GWARnOlhd4+6CFbER5YVYbaGMdI2Ul9i2O5t3ZpQY1cBKSwiHbIGwmqDNnwVHPOYkSvh7z+oUL7mPK0YkMv/cCgYEAt0YgudY5NszjWq2dEcIOah6LgNplx8DhY7cC0RsJeGgRh25FLwNk44r4Z6QNBfH8qRqdgUyf3G7e8CJ4lBwjkhIpEMzc60xJEHdmiT02RaQ0aQHtjABep8BeE68OjFu31BzZTbWvoDHPkk8GRu7iHmThrQ1Gr3nrrVQgIDEPCbMCgYEApRb8tfYsRAZGtjB0ZTEGiSgS5UtioxSVUPC8Mii37ic6Ak37qX7aGfRXppeQ6/28FbE0e5LmD+40p1ABQD+dNmRnWwCZxXOjBUYVRCFMbIwx4PiMerLaZ+l/lEXRa0vLxzGz6MGgSrKnNUcQgrUEEyrMiRLfi6Iccrzh/skLjy0CgYEA7ZW5pAqTrOzNXSxp3ZSiUk1OdVjmQNhzPedEvz7MMmuNz6Zb2stHi1WaE/JTPdQqZMcwYgmyASJ6jTrRByI0BXyAE0rOpUAtwiMmrN/rWqzTWaZZP8xdCUvglV5X1CCrEvZKYbquisxxOHJKKS8lTf9xIRJ+FGsuxfxnmktrcJI="
    # 支付宝公钥
    ALIPAY_PUBLIC_KEY: str = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAl+rj8MuX4Ih0w5n1DsAuHKa+PIhhiGXz1DthsHze8hdIgw8OjrSfckV8xX2f21GjoGBntW7PcYyRP5rfu0Of3mNMuBkkXMA+nV2l43VsPaqlP+4L5I7CHzHmyrZj8Lz+nNc4rklw38gk7PNTUR/48Ig7XYs/cXcdnJZXx7ikJ9dDVVD8yz4tFTNr9k0rtviHDWOkp6b+HT4ISmYfcfAE59q60AduhKsh1albUhrUbwD7xWPkfD4UdXxDsh2RwU8OaVT5oBup95E0AjtEK+nc9JujPn+d0wFTJdF4BRfsTb9K3FaQFlOVu4SGuVuJG/NHF2aIfDx/9ERVH5ek4prDNwIDAQAB"
    ALIPAY_RETURN_URL: str = "https://www.baidu.com/"  # 支付成功后的同步跳转URL (前端页面)
    ALIPAY_NOTIFY_URL: str = "https://c4ba-223-159-70-244.ngrok-free.app/api/v1/payment/alipay/notify"  # 支付结果异步通知URL (后端API)
    ALIPAY_DEBUG: bool = True  # True为沙箱环境, False为正式环境

    # Celery配置
    CELERY_BROKER_URL: str = "redis://:123456@localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://:123456@localhost:6379/1"

    # Celery任务
    CELERY_TASK_CREATE_SECKILL_ORDER: str = "app.tasks.seckill_tasks.create_seckill_order_task"


settings = Settings()

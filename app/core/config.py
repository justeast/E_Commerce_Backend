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


settings = Settings()

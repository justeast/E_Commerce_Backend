from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""

    # API配置
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:qqabc20040520@localhost:3306/for_ecommerce_backend"


settings = Settings()
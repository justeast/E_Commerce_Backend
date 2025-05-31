from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

import jwt
from passlib.context import CryptContext

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT相关配置
SECRET_KEY = "e9789b5309e3176b467a2971e8bbb2fe71fa820e3154a962f401b8a359974be5"  # 生产环境应使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 令牌黑名单前缀
TOKEN_BLACKLIST_PREFIX = "token:blacklist:"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(
        subject: str | Any, expires_delta: Optional[timedelta] = None
) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
        subject: str | Any, expires_delta: Optional[timedelta] = None
) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """解码令牌"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


async def add_token_to_blacklist(token: str, redis_pool) -> None:
    """
    将令牌添加到黑名单
    """
    try:
        # 解码令牌获取过期时间
        payload = decode_token(token)
        exp_timestamp = payload.get("exp")

        if exp_timestamp:
            # 计算令牌剩余有效期（秒）
            current_timestamp = datetime.now(timezone.utc).timestamp()
            ttl = max(int(exp_timestamp - current_timestamp), 0)

            # 将令牌添加到Redis黑名单，并设置过期时间(令牌过期时间到达时，Redis自动删除该令牌记录)
            key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
            await redis_pool.set(key, "1", ex=ttl)  # 1 表示令牌已添加到黑名单
    except Exception as e:
        # 如果令牌无效或已过期，则不需要添加到黑名单
        print(f"添加令牌到黑名单失败: {str(e)}")


async def is_token_blacklisted(token: str, redis_pool) -> bool:
    """
    检查令牌是否在黑名单中
    """
    key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
    return await redis_pool.exists(key) > 0

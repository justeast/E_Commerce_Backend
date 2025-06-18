import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Enum as SAEnum,
    JSON,
    Numeric,
)
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class PromotionTargetType(str, enum.Enum):
    ALL = "ALL"  # 全场通用
    PRODUCT = "PRODUCT"  # 指定商品
    CATEGORY = "CATEGORY"  # 指定分类
    TAG = "TAG"  # 指定标签


class PromotionConditionType(str, enum.Enum):
    NO_THRESHOLD = "NO_THRESHOLD"  # 无门槛
    MIN_AMOUNT = "MIN_AMOUNT"  # 满金额
    MIN_QUANTITY = "MIN_QUANTITY"  # 满件数


class PromotionActionType(str, enum.Enum):
    FIXED = "FIXED"  # 满减固定金额
    PERCENTAGE = "PERCENTAGE"  # 折扣
    SINGLE_PRODUCT_BUY_N_GET_M_FREE = "SINGLE_PRODUCT_BUY_N_GET_M_FREE"  # 单品满N件减M件

class Promotion(Base):
    __tablename__ = "promotion"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="促销活动名称")
    description = Column(String(255), comment="促销活动描述")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=False, comment="结束时间")
    is_active = Column(Boolean, default=True, comment="是否激活")

    target_type = Column(
        SAEnum(PromotionTargetType),
        nullable=False,
        default=PromotionTargetType.ALL,
        comment="促销适用目标类型",
    )
    target_ids = Column(JSON, comment="目标ID列表，根据target_type决定内容")

    condition_type = Column(
        SAEnum(PromotionConditionType),
        nullable=False,
        default=PromotionConditionType.NO_THRESHOLD,
        comment="触发条件类型",
    )
    condition_value = Column(
        Numeric(10, 2), comment="触发条件的值（如满100元，则为100）"
    )

    action_type = Column(
        SAEnum(PromotionActionType), nullable=False, comment="优惠动作类型"
    )
    action_value = Column(
        Numeric(10, 2),
        nullable=False,
        comment="优惠动作的值（如减10元则为10，打8折则为80）",
    )

    orders = relationship("Order", back_populates="promotion")

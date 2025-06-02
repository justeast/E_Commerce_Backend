from typing import Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_review import ProductReview
from app.models.product_attribute import SKU, AttributeValue
from app.utils.elasticsearch_connect import index_product, update_product_index, delete_product_index


async def prepare_product_for_indexing(db: AsyncSession, product: Product) -> Dict[str, Any]:
    """
    将数据库中的商品对象转换为适合索引的字典格式
    """
    # 计算平均评分和评价数量
    review_stats = await db.execute(
        select(
            func.avg(ProductReview.rating).label("avg_rating"),
            func.count(ProductReview.id).label("review_count")
        ).where(ProductReview.product_id == product.id)
    )
    stats = review_stats.first()
    avg_rating = float(stats[0]) if stats[0] is not None else 0.0
    review_count = stats[1] if stats[1] is not None else 0

    # 准备标签数据
    tags = [{"id": tag.id, "name": tag.name} for tag in product.tags]

    # 准备SKU数据
    skus = []
    for sku in product.skus:
        sku_data = {
            "id": sku.id,
            "name": sku.name,
            "code": sku.code,
            "price": sku.price,
            "stock": sku.stock,
            "attribute_values": []
        }

        # 收集SKU的属性值
        for attr_value in sku.attribute_values:
            sku_data["attribute_values"].append({
                "attribute_name": attr_value.attribute.name,
                "value": attr_value.value
            })

        skus.append(sku_data)

    # 收集所有属性和属性值
    attributes = {}
    for sku in product.skus:
        for attr_value in sku.attribute_values:
            attr_name = attr_value.attribute.name
            if attr_name not in attributes:
                attributes[attr_name] = []
            if attr_value.value not in attributes[attr_name]:
                attributes[attr_name].append(attr_value.value)

    # 转换属性为列表格式
    attributes_list = [
        {"name": name, "values": values}
        for name, values in attributes.items()
    ]

    # 构建索引文档
    product_data = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "category_id": product.category_id,
        "category_name": product.category.name,
        "is_active": product.is_active,
        "tags": tags,
        "attributes": attributes_list,
        "skus": skus,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat()
    }

    return product_data


async def index_single_product(db: AsyncSession, product_id: int) -> Dict[str, Any]:
    """
    索引单个商品
    """
    # 查询商品及其关联数据
    query = select(Product).where(Product.id == product_id)
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags),
        selectinload(Product.skus).selectinload(SKU.attribute_values).selectinload(
            AttributeValue.attribute)
    )

    result = await db.execute(query)
    product = result.scalars().first()

    if not product:
        raise ValueError(f"商品ID {product_id} 不存在")

    # 准备索引数据
    product_data = await prepare_product_for_indexing(db, product)

    # 索引到Elasticsearch
    response = await index_product(product_data)

    return response


async def update_product_in_index(db: AsyncSession, product_id: int) -> Dict[str, Any]:
    """
    更新索引中的商品
    """
    # 查询商品及其关联数据
    # 查询商品及其关联数据
    query = select(Product).where(Product.id == product_id)
    query = query.options(
        selectinload(Product.category),
        selectinload(Product.tags),
        selectinload(Product.skus).selectinload(SKU.attribute_values).selectinload(
            AttributeValue.attribute)
    )

    result = await db.execute(query)
    product = result.scalars().first()

    if not product:
        raise ValueError(f"商品ID {product_id} 不存在")

    # 准备索引数据
    product_data = await prepare_product_for_indexing(db, product)

    # 更新Elasticsearch索引
    try:
        response = await update_product_index(product_id, product_data)
    except Exception:
        # 如果更新失败（可能是文档不存在），则创建新文档
        response = await index_product(product_data)

    return response


async def delete_product_from_index(product_id: int) -> Dict[str, Any]:
    """
    从索引中删除商品
    """
    try:
        response = await delete_product_index(product_id)
        return response
    except Exception as e:
        # 如果文档不存在，可能会抛出异常
        return {"result": "not_found", "error": str(e)}


async def bulk_index_products(db: AsyncSession, batch_size: int = 100) -> int:
    """
    批量索引所有商品

    返回索引的商品数量
    """
    # 分批查询所有商品
    offset = 0
    total_indexed = 0

    while True:
        # 查询一批商品
        query = select(Product).offset(offset).limit(batch_size)
        query = query.options(
            selectinload(Product.category),
            selectinload(Product.tags),
            selectinload(Product.skus).selectinload(SKU.attribute_values).selectinload(
                AttributeValue.attribute)
        )

        result = await db.execute(query)
        products = result.scalars().all()

        if not products:
            break

        # 索引这批商品
        for product in products:
            product_data = await prepare_product_for_indexing(db, product)
            await index_product(product_data)
            total_indexed += 1

        # 更新偏移量
        offset += batch_size

    return total_indexed

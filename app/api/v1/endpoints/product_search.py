from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import has_permission
from app.db.session import get_db
from app.models.user import User
from app.utils.elasticsearch_connect import search_products
from app.schemas.product import ProductSearchResult, ProductSearchResponse, SearchSKU
from app.utils.product_indexer import bulk_index_products

router = APIRouter()


class AttributeFilter(BaseModel):
    """属性筛选模型"""
    name: str
    values: List[str]


@router.get("/", response_model=ProductSearchResponse)
async def search_products_api(
        q: Optional[str] = None,
        category_id: Optional[int] = None,
        tag_ids: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        highlight: bool = True,
        attributes: Optional[List[AttributeFilter]] = None,
):
    """
    商品搜索
    :param q: 搜索关键词
    :param category_id: 分类ID
    :param tag_ids: 标签ID列表
    :param price_min: 最低价格
    :param price_max: 最高价格
    :param sort_by: 排序字段，如 "price", "created_at", "avg_rating"
    :param sort_order: 排序方向，"asc" 或 "desc"
    :param page: 页码
    :param size: 每页数量
    :param highlight: 是否启用高亮功能,默认启用
    :param attributes: 属性筛选列表(复杂属性筛选的话，建议使用POST接口product_search/advanced)
    :return: 商品搜索结果
    """
    # 处理标签ID列表
    tag_ids_list = None
    if tag_ids:
        try:
            tag_ids_list = [int(tag_id.strip()) for tag_id in tag_ids.split(",") if tag_id.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="标签ID格式错误，应为逗号分隔的整数列表，如'1,4,7'"
            )

    # 将属性筛选列表转换为字典格式
    attributes_dict = {}
    if attributes:
        for attr in attributes:
            attributes_dict[attr.name] = attr.values

    try:
        # 调用Elasticsearch搜索
        search_result = await search_products(
            query=q,
            category_id=category_id,
            tag_ids=tag_ids_list,
            price_min=price_min,
            price_max=price_max,
            attributes=attributes_dict,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            size=size,
            highlight=highlight
        )

        # 解析搜索结果
        hits = search_result.get("hits", {})
        total = hits.get("total", {}).get("value", 0)  # 总记录数
        items = []

        for hit in hits.get("hits", []):  # 当前页记录
            source = hit.get("_source", {})
            item = ProductSearchResult(**source)

            # 处理高亮结果
            if highlight and "highlight" in hit:
                highlight_data = hit["highlight"]

                # 处理商品名称高亮
                if "name" in highlight_data:
                    item.highlight_name = highlight_data["name"][0]

                # 处理商品描述高亮
                if "description" in highlight_data:
                    item.highlight_description = " ... ".join(highlight_data["description"])

                # 处理SKU名称高亮
                if "skus.name" in highlight_data:
                    # 获取所有SKU名称的高亮结果
                    sku_highlights = highlight_data["skus.name"]
                    # 如果有SKU
                    if item.skus and len(item.skus) > 0:
                        # 为每个SKU创建一个新的SearchSKU对象，确保高亮字段被正确序列化
                        new_skus = []

                        # 从查询中提取关键词
                        keywords = q.split() if q else []

                        for sku in item.skus:
                            # 创建一个新的SKU对象，复制所有属性
                            new_sku = SearchSKU(
                                id=sku.id,
                                name=sku.name,
                                code=sku.code,
                                price=sku.price,
                                stock=sku.stock,
                                attribute_values=sku.attribute_values,
                                highlight_name=sku.name  # 默认使用原始名称
                            )

                            # 首先尝试使用Elasticsearch返回的高亮结果
                            for highlight_text in sku_highlights:
                                plain_highlight = highlight_text.replace("<em>", "").replace("</em>", "")
                                if plain_highlight in sku.name:
                                    # 创建高亮版本，替换原始文本为高亮文本
                                    new_sku.highlight_name = new_sku.highlight_name.replace(plain_highlight,
                                                                                            highlight_text)

                            # 如果没有匹配到高亮结果，尝试直接使用关键词
                            if new_sku.highlight_name == sku.name and keywords:
                                for keyword in keywords:
                                    if keyword in sku.name:
                                        new_sku.highlight_name = new_sku.highlight_name.replace(
                                            keyword, f"<em>{keyword}</em>")

                            new_skus.append(new_sku)

                        # 替换原始SKU列表
                        item.skus = new_skus
            items.append(item)

        # 构建响应
        return ProductSearchResponse(
            total=total,
            page=page,
            size=size,
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


class SearchRequest(BaseModel):
    """搜索请求模型"""
    q: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"
    page: int = 1
    size: int = 10
    highlight: bool = True
    attributes: Optional[List[AttributeFilter]] = None


@router.post("/advanced", response_model=ProductSearchResponse)
async def search_products_post_api(
        search_request: SearchRequest
):
    """
    商品搜索POST接口，支持复杂的属性筛选

    请求体示例:
    ```json
    {
        "q": "手机",
        "category_id": 1,
        "tag_ids": "1,2,3",
        "price_min": 100,
        "price_max": 1000,
        "attributes": [
            {"name": "颜色", "values": ["红色", "蓝色"]},
            {"name": "尺寸", "values": ["S", "M"]}
        ],
        "sort_by": "price",
        "sort_order": "asc",
        "page": 1,
        "size": 10,
        "highlight": true
    }
    ```
    """
    # 处理标签ID列表
    tag_ids_list = None
    if search_request.tag_ids:
        try:
            tag_ids_list = [int(tag_id.strip()) for tag_id in search_request.tag_ids.split(",") if tag_id.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="标签ID格式错误，应为逗号分隔的整数列表，如'1,4,7'"
            )

    # 将属性筛选列表转换为字典格式
    attributes_dict = {}
    if search_request.attributes:
        for attr in search_request.attributes:
            attributes_dict[attr.name] = attr.values

    try:
        # 调用Elasticsearch搜索
        search_result = await search_products(
            query=search_request.q,
            category_id=search_request.category_id,
            tag_ids=tag_ids_list,
            price_min=search_request.price_min,
            price_max=search_request.price_max,
            attributes=attributes_dict,
            sort_by=search_request.sort_by,
            sort_order=search_request.sort_order,
            page=search_request.page,
            size=search_request.size,
            highlight=search_request.highlight
        )

        # 解析搜索结果
        hits = search_result.get("hits", {})
        total = hits.get("total", {}).get("value", 0)  # 总记录数
        items = []

        for hit in hits.get("hits", []):  # 当前页记录
            source = hit.get("_source", {})
            item = ProductSearchResult(**source)

            # 处理高亮结果
            if search_request.highlight and "highlight" in hit:
                highlight_data = hit["highlight"]

                # 处理商品名称高亮
                if "name" in highlight_data:
                    item.highlight_name = highlight_data["name"][0]

                # 处理商品描述高亮
                if "description" in highlight_data:
                    item.highlight_description = " ... ".join(highlight_data["description"])

                # 处理SKU名称高亮
                if "skus.name" in highlight_data:
                    # 获取所有SKU名称的高亮结果
                    sku_highlights = highlight_data["skus.name"]

                    # 如果有SKU
                    if item.skus and len(item.skus) > 0:
                        # 为每个SKU创建一个新的SearchSKU对象，确保高亮字段被正确序列化
                        new_skus = []

                        # 从查询中提取关键词
                        keywords = search_request.q.split() if search_request.q else []

                        for sku in item.skus:
                            # 创建一个新的SKU对象，复制所有属性
                            new_sku = SearchSKU(
                                id=sku.id,
                                name=sku.name,
                                code=sku.code,
                                price=sku.price,
                                stock=sku.stock,
                                attribute_values=sku.attribute_values,
                                highlight_name=sku.name  # 默认使用原始名称
                            )

                            # 首先尝试使用Elasticsearch返回的高亮结果
                            for highlight_text in sku_highlights:
                                plain_highlight = highlight_text.replace("<em>", "").replace("</em>", "")
                                if plain_highlight in sku.name:
                                    # 创建高亮版本，替换原始文本为高亮文本
                                    new_sku.highlight_name = new_sku.highlight_name.replace(plain_highlight,
                                                                                            highlight_text)

                            # 如果没有匹配到高亮结果，尝试直接使用关键词
                            if new_sku.highlight_name == sku.name and keywords:
                                for keyword in keywords:
                                    if keyword in sku.name:
                                        new_sku.highlight_name = new_sku.highlight_name.replace(
                                            keyword, f"<em>{keyword}</em>")

                            new_skus.append(new_sku)

                        # 替换原始SKU列表
                        item.skus = new_skus
            items.append(item)

        # 构建响应
        return ProductSearchResponse(
            total=total,
            page=search_request.page,
            size=search_request.size,
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/reindex-all", status_code=202)
async def reindex_all_products_api(
        db: AsyncSession = Depends(get_db),
        _: User = Depends(has_permission("product_manage"))
):
    """
    重新索引所有商品到Elasticsearch
    """
    try:
        # 异步执行批量索引
        total_indexed = await bulk_index_products(db)
        return {"message": f"成功重新索引 {total_indexed} 个商品"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"重新索引过程中出错: {str(e)}"
        )

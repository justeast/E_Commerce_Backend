from elasticsearch import AsyncElasticsearch
from functools import lru_cache
from typing import Optional, Dict, Any, List

from app.core.config import settings


@lru_cache()
def get_elasticsearch_client() -> AsyncElasticsearch:
    """
    获取Elasticsearch客户端实例（单例模式）
    """
    # 构建连接参数
    connection_params = {
        "hosts": settings.ELASTICSEARCH_HOSTS,
        "verify_certs": settings.ELASTICSEARCH_VERIFY_CERTS,
    }

    # 添加可选参数
    if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
        connection_params["basic_auth"] = (
            settings.ELASTICSEARCH_USERNAME,
            settings.ELASTICSEARCH_PASSWORD
        )

    if settings.ELASTICSEARCH_CA_CERTS:
        connection_params["ca_certs"] = settings.ELASTICSEARCH_CA_CERTS

    # 创建客户端
    return AsyncElasticsearch(**connection_params)


async def close_elasticsearch_connection() -> None:
    """
    关闭Elasticsearch连接
    """
    client = get_elasticsearch_client()
    await client.close()


async def index_exists() -> bool:
    """
    检查商品索引是否存在

    返回:
        bool: 索引是否存在
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX
    return await client.indices.exists(index=index_name)


# 商品索引映射定义
PRODUCT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "integer"},
            "name": {
                "type": "text",
                "analyzer": "ik_max_word",  # 使用IK分词器
                "search_analyzer": "ik_smart",
                "fields": {
                    "keyword": {"type": "keyword"}  # 用于精确匹配和排序
                }
            },
            "description": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_smart"
            },
            "price": {"type": "float"},
            "category_id": {"type": "integer"},
            "category_name": {"type": "keyword"},
            "is_active": {"type": "boolean"},
            "stock": {"type": "integer"},
            "tags": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "keyword"}
                }
            },
            "attributes": {
                "type": "nested",
                "properties": {
                    "name": {"type": "keyword"},
                    "values": {"type": "keyword"}
                }
            },
            "skus": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "code": {"type": "keyword"},
                    "price": {"type": "float"},
                    "stock": {"type": "integer"},
                    "attribute_values": {
                        "type": "nested",
                        "properties": {
                            "attribute_name": {"type": "keyword"},
                            "value": {"type": "keyword"}
                        }
                    }
                }
            },
            "avg_rating": {"type": "float"},
            "review_count": {"type": "integer"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"}
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    }
}


async def create_product_index() -> None:
    """
    创建商品索引（如果不存在）
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX

    # 检查索引是否存在
    if not await client.indices.exists(index=index_name):
        # 创建索引
        await client.indices.create(
            index=index_name,
            body=PRODUCT_INDEX_MAPPING
        )
        print(f"创建索引 '{index_name}' 成功")
    else:
        print(f"索引 '{index_name}' 已存在")


async def index_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    索引单个商品数据
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX

    # 索引文档
    response = await client.index(
        index=index_name,
        id=str(product_data["id"]),
        document=product_data,
        refresh=True  # 立即刷新，使文档可搜索
    )

    return response


async def update_product_index(product_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新商品索引
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX

    # 更新文档
    response = await client.update(
        index=index_name,
        id=str(product_id),
        doc=product_data,
        refresh=True
    )

    return response


async def delete_product_index(product_id: int) -> Dict[str, Any]:
    """
    删除商品索引
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX

    # 删除文档
    response = await client.delete(
        index=index_name,
        id=str(product_id),
        refresh=True
    )

    return response


async def search_products(
        query: Optional[str] = None,
        category_id: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        attributes: Optional[Dict[str, List[str]]] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        page: int = 1,
        size: int = 10,
        highlight: bool = True
) -> Dict[str, Any]:
    """
    搜索商品

    参数:
        query: 搜索关键词
        category_id: 分类ID
        tag_ids: 标签ID列表
        price_min: 最低价格
        price_max: 最高价格
        attributes: 属性筛选，格式为 {"颜色": ["红色", "蓝色"], "尺寸": ["S", "M"]}
        sort_by: 排序字段，如 "price", "created_at", "avg_rating"
        sort_order: 排序方向，"asc" 或 "desc"
        page: 页码
        size: 每页数量
        highlight: 是否启用高亮功能
    """
    client = get_elasticsearch_client()
    index_name = settings.ELASTICSEARCH_PRODUCT_INDEX

    # 构建查询
    body = {
        "query": {
            "bool": {
                "must": [],
                "filter": []
            }
        },
        "from": (page - 1) * size,
        "size": size
    }

    # 关键词搜索
    if query:
        body["query"]["bool"]["must"].append({
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description", "skus.name"],
                "type": "best_fields"
            }
        })

        # 添加高亮配置
        if highlight:
            body["highlight"] = {
                "type": "unified",  # 使用unified highlighter
                "phrase_limit": 50,  # 增加短语识别限制
                "fields": {
                    "name": {"number_of_fragments": 0},
                    "description": {"number_of_fragments": 2, "fragment_size": 150},
                    "skus.name": {
                        "number_of_fragments": 0,  # 返回整个字段而不是片段
                        "type": "unified"  # 确保使用统一高亮器
                    }
                },
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "require_field_match": False  # 允许跨字段匹配
            }
    else:
        body["query"]["bool"]["must"].append({"match_all": {}})

    # 分类筛选
    if category_id is not None:
        body["query"]["bool"]["filter"].append({
            "term": {"category_id": category_id}
        })

    # 标签筛选
    if tag_ids:
        body["query"]["bool"]["filter"].append({
            "nested": {
                "path": "tags",
                "query": {
                    "terms": {"tags.id": tag_ids}
                }
            }
        })

    # 价格范围筛选
    price_range = {}
    if price_min is not None:
        price_range["gte"] = price_min
    if price_max is not None:
        price_range["lte"] = price_max
    if price_range:
        body["query"]["bool"]["filter"].append({
            "range": {"price": price_range}
        })

    # 属性筛选
    if attributes:
        for attr_name, attr_values in attributes.items():
            body["query"]["bool"]["filter"].append({
                "nested": {
                    "path": "attributes",
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"attributes.name": attr_name}},
                                {"terms": {"attributes.values": attr_values}}
                            ]
                        }
                    }
                }
            })

    # 只显示上架商品
    body["query"]["bool"]["filter"].append({
        "term": {"is_active": True}
    })

    # 排序
    if sort_by:
        sort_field = sort_by
        if sort_by == "name":
            sort_field = "name.keyword"  # 使用keyword字段排序

        body["sort"] = [{sort_field: {"order": sort_order}}]

    # 执行搜索
    response = await client.search(
        index=index_name,
        body=body
    )

    return response

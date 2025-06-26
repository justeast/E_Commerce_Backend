本项目各模块API均经postman测试跑通，API文档页：https://justeast.github.io/E_Commerce_Backend/api_docs.html

- 技术栈：FastAPI + SQLAlchemy + MySQL + Redis + Celery + RabbitMQ等
- 模块覆盖“商品-库存-促销-订单-支付-用户行为分析”等，以下是主要实现点(图片仅为部分实现展示)：
  - OAuth2 + JWT + RBAC权限,完成用户登录认证和接口鉴权.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/rbac.png)
    
  - Elasticsearch + IK分词动态索引， 实现对商品的快速搜索、 关键字查询和高亮匹配显示.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/elasticsearch.png)
    
  - Redis分布式锁 + Lua脚本， 实现原子库存扣减， 保证并发下库存零超卖， 配合RabbitMQ完成低库存预警自动邮箱推送.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/redislock.png)
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/rabbitmq.png)

  - Celery Tasks + Redis， 完成秒杀活动预热和秒杀订单的异步创建； 配合Celery Beat定时任务， 实现活动状态的自动流转
和超时订单的自动取消.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/celery_tasks.png)

  - 支付宝alipay集成.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/alipay.png)

  - 用户浏览历史实时写入Redis,离线 Celery Beat 每日定时生成商品相似度并基于浏览偏好自动打标签(兴趣类别/活跃度)， 实现
个性化商品推荐和用户画像构建.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/redis_record.png)

  - postman模块测试.
    ![图片](https://github.com/justeast/E_Commerce_Backend/blob/master/img_readme/postman_test.png)
    

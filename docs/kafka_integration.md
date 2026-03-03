# Kafka 集成说明 🎯

快速说明如何在本地测试爬虫发送到 Kafka 的能力，以及相关环境变量和依赖。

## 依赖
- Python: 推荐 3.8+
- 安装 kafka-python: `pip install kafka-python`

## 环境变量（可选）
- KAFKA_BOOTSTRAP_SERVERS (默认 `localhost:9092`)
- KAFKA_TOPIC (默认 `weibo.hotsearch`)

## 本地快速启动（使用 Docker Compose）
简单示例（在本机已有 docker 的情况下）:

```yaml
version: '3.7'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.2.1
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
  kafka:
    image: confluentinc/cp-kafka:7.2.1
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
    ports:
      - '9092:9092'
```

启动后可使用 kafka-console-consumer 查看 topic:
```
# 进入容器或使用本机安装的 kafka 工具
kafka-console-consumer --bootstrap-server localhost:9092 --topic weibo.hotsearch --from-beginning
```

## 测试发送
1. 启动 Kafka
2. 设置环境变量（如需要）: `export KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
3. 在项目根目录运行：
```
python tools/kafka_test_producer.py
```
4. 在消费者终端（`kafka-console-consumer`）确认是否收到消息

## 注意
- 我们当前使用 `kafka-python` 作为 Producer 简单实现；生产环境可考虑 `confluent-kafka`（需要 librdkafka）。
- 若 Kafka 未配置或不可用，爬虫会降级为记录日志并继续保存到 Redis/MySQL（不会中断爬取流程）。

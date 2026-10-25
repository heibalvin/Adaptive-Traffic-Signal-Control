"""
Kafka communication layer for publish/subscribe events.

Topics:
- traffic.light.events   (outbound events from devices)
- traffic.light.commands (inbound commands to devices)
- traffic.light.agent   (agent-level events)
"""
import json
import logging
from typing import Optional, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError, KafkaTimeoutError

logger = logging.getLogger(__name__)

# Topic names
TOPIC_EVENTS = "traffic.light.events"
TOPIC_COMMANDS = "traffic.light.commands"
TOPIC_AGENT = "traffic.light.agent"


class KafkaConfig:
    def __init__(self, bootstrap_servers: str, client_id: str = "atcs"):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id


class KafkaPublisher:
    """Publish events to Kafka topics."""

    def __init__(self, config: KafkaConfig):
        self.config = config
        self.producer: Optional[KafkaProducer] = None

    def connect(self):
        self.producer = KafkaProducer(
            bootstrap_servers=self.config.bootstrap_servers,
            client_id=self.config.client_id,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
        )
        logger.info(f"Kafka publisher connected to {self.config.bootstrap_servers}")

    def publish(self, topic: str, message: dict, key: Optional[str] = None):
        if not self.producer:
            raise RuntimeError("Publisher not connected")
        try:
            future = self.producer.send(
                topic,
                value=message,
                key=key.encode("utf-8") if key else None
            )
            future.get(timeout=10)
            logger.debug(f"Published to {topic}: {message}")
        except KafkaTimeoutError as e:
            logger.error(f"Timeout publishing to {topic}: {e}")
            raise

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
            self.producer = None


class KafkaSubscriber:
    """Subscribe to Kafka topics for events and commands."""

    def __init__(self, config: KafkaConfig, group_id: str):
        self.config = config
        self.group_id = group_id
        self.consumer: Optional[KafkaConsumer] = None
        self._running = False

    def connect(self, topics: list[str]):
        self.consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=self.config.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        logger.info(f"Kafka subscriber connected to {topics} (group={self.group_id})")

    def poll(self, timeout_ms: int = 1000) -> list[dict]:
        if not self.consumer:
            raise RuntimeError("Subscriber not connected")
        messages = []
        try:
            records = self.consumer.poll(timeout_ms=timeout_ms, max_records=100)
            for tp, batch in records.items():
                for msg in batch:
                    messages.append(msg.value)
        except KafkaError as e:
            logger.error(f"Kafka poll error: {e}")
        return messages

    def close(self):
        if self.consumer:
            self.consumer.close()
            self.consumer = None


def ensure_topics(config: KafkaConfig, topic_names: list[str]):
    """Create topics if they don't exist."""
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=config.bootstrap_servers,
            client_id=config.client_id + "-admin"
        )
        existing = admin.list_topics()
        topics_to_create = [
            NewTopic(name=name, num_partitions=3, replication_factor=1)
            for name in topic_names
            if name not in existing
        ]
        if topics_to_create:
            admin.create_topics(topics_to_create)
            logger.info(f"Created topics: {[t.name for t in topics_to_create]}")
        admin.close()
    except Exception as e:
        logger.warning(f"Could not ensure topics: {e}")


def bootstrap_servers_from_env() -> str:
    """Build bootstrap servers string from environment."""
    import os
    host = os.environ.get("KAFKA_HOST", "aicd_kafka")
    return f"{host}:9092"
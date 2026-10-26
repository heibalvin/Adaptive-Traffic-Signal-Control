import json
from kafka import KafkaConsumer
from kafka_utils.config import KAFKA_BOOTSTRAP_SERVERS


class KafkaConsumerClient:
    def __init__(self, topics, group_id=None):
        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id=group_id,
                consumer_timeout_ms=2000
            )
        except Exception as e:
            print(f"[KAFKA] Consumer init error: {e}")
            self.consumer = None

    def poll_messages(self, timeout_ms=1000):
        if self.consumer is None:
            return []
        try:
            messages = self.consumer.poll(timeout_ms=timeout_ms)
            result = []
            for topic_partition, msgs in messages.items():
                for msg in msgs:
                    result.append(msg.value)
            return result
        except Exception as e:
            print(f"[KAFKA] Poll error: {e}")
            return []

    def close(self):
        if self.consumer:
            self.consumer.close()

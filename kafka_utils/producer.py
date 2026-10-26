import json
from kafka import KafkaProducer
from kafka_utils.config import KAFKA_BOOTSTRAP_SERVERS


class KafkaProducerClient:
    def __init__(self):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=10000,
                max_block_ms=10000
            )
        except Exception as e:
            print(f"[KAFKA] Producer init error: {e}")
            self.producer = None

    def send_message(self, topic, message):
        if self.producer is None:
            return
        try:
            self.producer.send(topic, message)
            self.producer.flush(timeout=10)
        except Exception as e:
            print(f"[KAFKA] Send error: {e}")

    def close(self):
        if self.producer:
            self.producer.close()

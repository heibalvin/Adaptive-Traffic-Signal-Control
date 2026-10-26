import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_HOST = os.getenv("KAFKA_HOST", "aicd_kafka")
KAFKA_PORT = os.getenv("KAFKA_PORT", "9092")
KAFKA_BOOTSTRAP_SERVERS = f"{KAFKA_HOST}:{KAFKA_PORT}"

# Topics
TOPIC_DEVICE_OUTBOUND = "traffic.device.outbound"
TOPIC_GROUP_INBOUND = "traffic.group.inbound"

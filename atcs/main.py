"""
ATCS - Adaptive Traffic Signal Control
Main entry point.
"""
import os
import sys
import time
import logging
import threading

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from atcs.services.traffic_light_agent import TrafficLightAgent
from atcs.services.kafka_comm import (
    KafkaConfig, KafkaPublisher, ensure_topics,
    TOPIC_EVENTS, TOPIC_COMMANDS, TOPIC_AGENT, bootstrap_servers_from_env
)
from atcs.services.postgres_store import PostgresStore
from atcs.models.traffic_light_device import TrafficLightDevice, TimerConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("atcs")


def run_device(device_id: str, timer_config: TimerConfig = None):
    """Run a standalone traffic light device."""
    logger.info(f"Starting device {device_id}")
    device = TrafficLightDevice(device_id, timer_config)

    # Connect to Kafka to publish events
    kafka_config = KafkaConfig(bootstrap_servers_from_env())
    publisher = KafkaPublisher(kafka_config)
    publisher.connect()

    # Wire device events to Kafka
    def on_state_change(state):
        event = device.has_change_state(state)
        publisher.publish(TOPIC_EVENTS, event)
        logger.info(f"[{device_id}] State -> {state.value}")

    def on_colour_change(colour):
        event = device.has_changed_colour(colour)
        publisher.publish(TOPIC_EVENTS, event)
        logger.info(f"[{device_id}] Colour -> {colour.value}")

    device.on_state_change(on_state_change)
    device.on_colour_change(on_colour_change)

    # Persist to Postgres
    try:
        pg = PostgresStore()
        pg.connect()
        pg.save_device(device.to_dict())
    except Exception as e:
        logger.warning(f"Postgres not available: {e}")

    device.start()

    # Also consume commands for this device
    from atcs.services.kafka_comm import KafkaSubscriber
    subscriber = KafkaSubscriber(kafka_config, group_id=f"device-{device_id}")
    subscriber.connect([TOPIC_COMMANDS])

    try:
        while True:
            commands = subscriber.poll(timeout_ms=1000)
            for cmd in commands:
                if cmd.get("device_id") == device_id:
                    cmd_type = cmd.get("type")
                    if cmd_type == "willChangeTimer":
                        device.will_change_timer(cmd.get("colour"), cmd.get("timer"))
                    elif cmd_type == "willChangeState":
                        device.will_change_state(cmd.get("state"))
                    elif cmd_type == "willChangeColour":
                        device.will_change_colour(cmd.get("colour"))
            time.sleep(0.1)
    except KeyboardInterrupt:
        device.stop()
        publisher.close()
        subscriber.close()


def run_agent():
    """Run the traffic light agent."""
    agent = TrafficLightAgent()
    agent.start()

    # Create a demo device
    agent.create_device(device_id="tl-demo-001", timer_config=TimerConfig(green=30, orange=5, red=60))

    try:
        while True:
            time.sleep(10)
            devices = agent.list_devices()
            for d in devices:
                logger.info(f"Device {d['id']}: state={d['state']} colour={d['colour']}")
    except KeyboardInterrupt:
        agent.stop()


def run_web():
    """Run the web application."""
    from atcs.web.app import app, socketio, init_app
    init_app()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "agent"
    if mode == "device":
        device_id = sys.argv[2] if len(sys.argv) > 2 else "tl-001"
        run_device(device_id)
    elif mode == "agent":
        run_agent()
    elif mode == "web":
        run_web()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python -m atcs.main [device|agent|web] [device_id]")
        sys.exit(1)
"""
Traffic Light Agent - manages a fleet of traffic light devices.

The agent can create, read, update, and delete traffic light devices.
It communicates through Kafka topics and persists state to PostgreSQL.
"""
import os
import time
import uuid
import logging
import threading
from typing import Optional

from atcs.models.traffic_light_device import (
    TrafficLightDevice, Colour, State, TimerConfig
)
from atcs.services.kafka_comm import (
    KafkaConfig, KafkaPublisher, KafkaSubscriber,
    TOPIC_EVENTS, TOPIC_COMMANDS, TOPIC_AGENT,
    ensure_topics, bootstrap_servers_from_env
)
from atcs.services.postgres_store import PostgresConfig, PostgresStore

logger = logging.getLogger(__name__)


class TrafficLightAgent:
    """
    Manages a fleet of TrafficLightDevices.
    - Creates/starts/stops/deletes devices
    - Routes inbound commands to the correct device
    - Persists events to PostgreSQL
    - Publishes outbound events to Kafka
    """

    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.devices: dict[str, TrafficLightDevice] = {}
        self._lock = threading.Lock()

        # Kafka
        self.kafka_config = KafkaConfig(bootstrap_servers_from_env())
        self.publisher = KafkaPublisher(self.kafka_config)
        self.subscriber: Optional[KafkaSubscriber] = None

        # Postgres
        self.postgres = PostgresStore()

        # Running flag
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── lifecycle ──────────────────────────────────────────────────
    def start(self):
        """Start the agent: connect to Kafka, Postgres, and begin consuming commands."""
        logger.info(f"Starting TrafficLightAgent {self.agent_id}")

        # Ensure Kafka topics exist
        ensure_topics(self.kafka_config, [TOPIC_EVENTS, TOPIC_COMMANDS, TOPIC_AGENT])

        # Connect publisher
        self.publisher.connect()

        # Connect subscriber for commands
        self.subscriber = KafkaSubscriber(self.kafka_config, group_id=self.agent_id)
        self.subscriber.connect([TOPIC_COMMANDS])

        # Connect Postgres
        self.postgres.connect()

        # Start command consumer loop
        self._running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()

        logger.info(f"TrafficLightAgent {self.agent_id} started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.publisher.close()
        if self.subscriber:
            self.subscriber.close()
        self.postgres.close()
        logger.info(f"TrafficLightAgent {self.agent_id} stopped")

    # ── CRUD operations ────────────────────────────────────────────
    def create_device(self, device_id: Optional[str] = None,
                      timer_config: Optional[TimerConfig] = None) -> TrafficLightDevice:
        """Create a new traffic light device."""
        device_id = device_id or f"tl-{uuid.uuid4().hex[:8]}"
        with self._lock:
            if device_id in self.devices:
                raise ValueError(f"Device {device_id} already exists")
            device = TrafficLightDevice(device_id, timer_config)
            device.on_state_change(self._on_device_state_change)
            device.on_colour_change(self._on_device_colour_change)
            self.devices[device_id] = device

        # Persist
        self.postgres.save_device(device.to_dict())

        # Publish creation event
        self.publisher.publish(TOPIC_EVENTS, {
            "type": "deviceCreated",
            "device_id": device_id,
            "timestamp": time.time()
        })

        # Start the device
        device.start()
        logger.info(f"Created device {device_id}")
        return device

    def get_device(self, device_id: str) -> Optional[TrafficLightDevice]:
        with self._lock:
            return self.devices.get(device_id)

    def list_devices(self) -> list[dict]:
        with self._lock:
            return [d.to_dict() for d in self.devices.values()]

    def delete_device(self, device_id: str):
        with self._lock:
            device = self.devices.pop(device_id, None)
            if device:
                device.stop()

        self.postgres.delete_device(device_id)

        # Publish deletion event
        self.publisher.publish(TOPIC_EVENTS, {
            "type": "deviceDeleted",
            "device_id": device_id,
            "timestamp": time.time()
        })
        logger.info(f"Deleted device {device_id}")

    # ── command routing ────────────────────────────────────────────
    def handle_command(self, command: dict):
        """Route an inbound command to the appropriate device."""
        device_id = command.get("device_id")
        cmd_type = command.get("type")
        if not device_id:
            logger.warning(f"Command missing device_id: {command}")
            return

        device = self.get_device(device_id)
        if not device:
            logger.warning(f"Command for unknown device {device_id}")
            return

        if cmd_type == "willChangeTimer":
            device.will_change_timer(command.get("colour"), command.get("timer"))
        elif cmd_type == "willChangeState":
            device.will_change_state(command.get("state"))
        elif cmd_type == "willChangeColour":
            device.will_change_colour(command.get("colour"))
        else:
            logger.warning(f"Unknown command type: {cmd_type}")

    # ── device event callbacks ─────────────────────────────────────
    def _on_device_state_change(self, state: State):
        """Called when a device changes state."""
        # Find which device triggered this
        for device in self.devices.values():
            if device.get_state() == state:
                event = device.has_change_state(state)
                self.postgres.save_event(event)
                self.publisher.publish(TOPIC_EVENTS, event)
                break

    def _on_device_colour_change(self, colour: Colour):
        """Called when a device changes colour."""
        for device in self.devices.values():
            if device.get_colour() == colour:
                event = device.has_changed_colour(colour)
                self.postgres.save_event(event)
                self.publisher.publish(TOPIC_EVENTS, event)
                break

    # ── consume loop ───────────────────────────────────────────────
    def _consume_loop(self):
        while self._running:
            try:
                commands = self.subscriber.poll(timeout_ms=1000)
                for cmd in commands:
                    self.handle_command(cmd)
            except Exception as e:
                logger.error(f"Error in consume loop: {e}")
                time.sleep(1)


def main():
    """Entry point for running the agent standalone."""
    logging.basicConfig(level=logging.INFO)
    agent = TrafficLightAgent()
    agent.start()

    # Create a demo device
    agent.create_device(device_id="demo-001")

    try:
        while True:
            time.sleep(10)
            devices = agent.list_devices()
            for d in devices:
                logger.info(f"Device {d['id']}: state={d['state']} colour={d['colour']}")
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
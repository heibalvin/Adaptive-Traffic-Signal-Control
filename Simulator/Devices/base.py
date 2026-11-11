"""Base device state machine and MQTT runtime."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..Common.mqtt import (
    DeviceState,
    Message,
    decode_payload,
    device_command_topic,
    device_telemetry_topic,
    publish_json,
)


try:  # optional runtime dependency
    import paho.mqtt.client as mqtt  # type: ignore
except Exception:  # pragma: no cover
    mqtt = None


@dataclass
class DeviceConfig:
    device_id: str
    device_type: str
    district_id: str
    intersection_id: str = "boundary"
    broker_host: str = "localhost"
    broker_port: int = 1883
    heartbeat_seconds: float = 5.0


class BaseDevice:
    def __init__(self, config: DeviceConfig, initial_payload: dict[str, Any] | None = None):
        self.config = config
        self.state = DeviceState.IDLE
        self.payload: dict[str, Any] = dict(initial_payload or {})
        self._lock = threading.RLock()
        self._running = False
        self._client: Any = None
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def telemetry_topic(self) -> str:
        c = self.config
        return device_telemetry_topic(c.district_id, c.intersection_id, c.device_type, c.device_id)

    @property
    def command_topic(self) -> str:
        c = self.config
        return device_command_topic(c.district_id, c.intersection_id, c.device_type, c.device_id)

    def transition(self, new_state: DeviceState, reason: str = "") -> None:
        with self._lock:
            self.state = new_state
            if reason:
                self.payload["last_transition_reason"] = reason
            self.payload["state"] = self.state.value
        self.publish_state("state_change")

    def apply_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Handle manager command; override in subclasses for device-specific vars."""
        action = str(command.get("action", "update")).lower()
        params = command.get("params") or {}
        if action in {"start", "activate"}:
            self.payload.update(params)
            self.transition(DeviceState.ACTIVE, action)
        elif action in {"stop", "deactivate"}:
            self.payload.update(params)
            self.transition(DeviceState.STOPPED, action)
        elif action == "ready":
            self.payload.update(params)
            self.transition(DeviceState.READY, action)
        elif action == "reset":
            self.payload.update(params)
            self.transition(DeviceState.IDLE, action)
        else:
            self.payload.update(params)
            self.payload["state"] = self.state.value
            self.publish_state("variable_update")
        return {"ok": True, "state": self.state.value, "payload": self.payload}

    def make_message(self, msg_type: str, extra: dict[str, Any] | None = None) -> Message:
        c = self.config
        body = dict(self.payload)
        if extra:
            body.update(extra)
        return Message(
            type=msg_type,
            device_type=c.device_type,
            device_id=c.device_id,
            district_id=c.district_id,
            intersection_id=c.intersection_id,
            state=self.state.value,
            payload=body,
            source="device",
        )

    def publish_state(self, msg_type: str = "telemetry", extra: dict[str, Any] | None = None) -> None:
        if not self._client:
            return
        publish_json(self._client, self.telemetry_topic, self.make_message(msg_type, extra))

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        client.subscribe(self.command_topic, qos=1)
        self.publish_state("online")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            command = decode_payload(msg.payload)
            result = self.apply_command(command)
            publish_json(client, self.telemetry_topic, self.make_message("command_ack", {"result": result}))
        except Exception as exc:
            publish_json(client, self.telemetry_topic, self.make_message("command_nack", {"error": str(exc)}))

    def _heartbeat_loop(self) -> None:
        while self._running:
            self.publish_state("heartbeat")
            time.sleep(max(0.5, self.config.heartbeat_seconds))

    def start(self) -> None:
        if mqtt is None:
            raise RuntimeError("paho-mqtt is required to run devices. Install: pip install paho-mqtt")
        if self._running:
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config.device_id) if hasattr(mqtt, "CallbackAPIVersion") else mqtt.Client(client_id=self.config.device_id)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self.config.broker_host, self.config.broker_port, keepalive=60)
        self._client = client
        self._running = True
        self.transition(DeviceState.READY, "start")
        client.loop_start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._client:
            self.transition(DeviceState.STOPPED, "stop")
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._client = None

"""Base manager: subscribes to device telemetry and publishes commands."""

from __future__ import annotations

import threading
from typing import Any, Callable

from ..Common.mqtt import decode_payload, device_command_topic, manager_telemetry_topic, publish_json

try:
    import paho.mqtt.client as mqtt  # type: ignore
except Exception:  # pragma: no cover
    mqtt = None


class BaseManager:
    def __init__(
        self,
        device_type: str,
        manager_id: str = "default",
        broker_host: str = "localhost",
        broker_port: int = 1883,
        district_id: str = "+",
        intersection_id: str = "+",
    ):
        self.device_type = device_type
        self.manager_id = manager_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.district_id = district_id
        self.intersection_id = intersection_id
        self.devices: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._client: Any = None
        self.on_telemetry: Callable[[str, dict[str, Any]], None] | None = None

    @property
    def telemetry_sub_topic(self) -> str:
        return f"devices/{self.district_id}/{self.intersection_id}/{self.device_type}/+/telemetry"

    @property
    def manager_topic(self) -> str:
        return manager_telemetry_topic(self.device_type, self.manager_id)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        client.subscribe(self.telemetry_sub_topic, qos=1)
        publish_json(client, self.manager_topic, {"type": "manager_online", "device_type": self.device_type, "manager_id": self.manager_id})

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            data = decode_payload(msg.payload)
            device_id = str(data.get("device_id") or msg.topic.split("/")[-2])
            with self._lock:
                self.devices[device_id] = data
            if self.on_telemetry:
                self.on_telemetry(msg.topic, data)
            publish_json(client, self.manager_topic, {"type": "device_telemetry", "device_id": device_id, "topic": msg.topic, "data": data})
        except Exception as exc:
            publish_json(client, self.manager_topic, {"type": "manager_error", "error": str(exc), "topic": getattr(msg, "topic", "")})

    def start(self) -> None:
        if mqtt is None:
            raise RuntimeError("paho-mqtt is required. Install: pip install paho-mqtt")
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.device_type}-manager-{self.manager_id}") if hasattr(mqtt, "CallbackAPIVersion") else mqtt.Client(client_id=f"{self.device_type}-manager-{self.manager_id}")
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self.broker_host, self.broker_port, keepalive=60)
        client.loop_start()
        self._client = client

    def stop(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._client = None

    def send_command(self, district_id: str, intersection_id: str, device_id: str, action: str, params: dict[str, Any] | None = None) -> None:
        if not self._client:
            raise RuntimeError("manager not started")
        topic = device_command_topic(district_id, intersection_id, self.device_type, device_id)
        publish_json(self._client, topic, {"action": action, "params": params or {}, "source": "manager", "manager_id": self.manager_id})

    def set_variables(self, district_id: str, intersection_id: str, device_id: str, **params: Any) -> None:
        self.send_command(district_id, intersection_id, device_id, "update", params)

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self.devices.get(device_id)

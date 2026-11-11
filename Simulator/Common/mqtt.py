"""MQTT topic and payload helpers for simulator devices/managers."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable


class DeviceType(str, Enum):
    GENERATOR = "generator"
    ABSORBER = "absorber"
    ROAD = "road"


class DeviceState(str, Enum):
    IDLE = "idle"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"
    STOPPED = "stopped"


def device_telemetry_topic(district_id: str, intersection_id: str, device_type: str, device_id: str) -> str:
    return f"devices/{district_id}/{intersection_id}/{device_type}/{device_id}/telemetry"


def device_command_topic(district_id: str, intersection_id: str, device_type: str, device_id: str) -> str:
    return f"devices/{district_id}/{intersection_id}/{device_type}/{device_id}/command"


def manager_telemetry_topic(device_type: str, manager_id: str = "default") -> str:
    return f"managers/{device_type}/{manager_id}/telemetry"


def manager_command_topic(device_type: str, manager_id: str = "default") -> str:
    return f"managers/{device_type}/{manager_id}/command"


@dataclass
class Message:
    type: str
    device_type: str
    device_id: str
    district_id: str
    intersection_id: str
    state: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=lambda: time.time())
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "device"  # device|manager

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @staticmethod
    def from_json(raw: str | bytes | bytearray) -> "Message":
        data = json.loads(raw)
        return Message(**data)


def publish_json(client: Any, topic: str, payload: dict[str, Any] | Message, qos: int = 1, retain: bool = False) -> None:
    if isinstance(payload, Message):
        body = payload.to_json()
    else:
        body = json.dumps(payload, separators=(",", ":"))
    client.publish(topic, body, qos=qos, retain=retain)


def decode_payload(raw: str | bytes | bytearray) -> dict[str, Any]:
    data = json.loads(raw)
    return data if isinstance(data, dict) else {"value": data}

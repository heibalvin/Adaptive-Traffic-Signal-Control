"""Road device: holds segment flow/capacity state."""

from __future__ import annotations

import argparse
from typing import Any

from .base import BaseDevice, DeviceConfig
from ..Common.mqtt import DeviceState, DeviceType


class RoadDevice(BaseDevice):
    def __init__(self, config: DeviceConfig):
        super().__init__(
            config,
            initial_payload={
                "from_intersection_id": None,
                "to_intersection_id": None,
                "capacity": 0.0,
                "speed_limit": 0.0,
                "current_flow": 0.0,
                "queue_length": 0.0,
                "occupancy": 0.0,
                "open": True,
            },
        )

    def apply_command(self, command: dict[str, Any]) -> dict[str, Any]:
        params = command.get("params") or {}
        for k in ("capacity", "speed_limit", "current_flow", "queue_length", "occupancy"):
            if k in params:
                params[k] = max(0.0, float(params[k]))
        if "open" in params:
            params["open"] = bool(params["open"])
        action = str(command.get("action", "")).lower()
        if action == "flow_update":
            flow = max(0.0, float(params.get("current_flow", self.payload.get("current_flow", 0.0))))
            cap = max(0.0, float(params.get("capacity", self.payload.get("capacity", 0.0))))
            self.payload.update(params)
            self.payload["current_flow"] = flow
            self.payload["capacity"] = cap
            self.payload["occupancy"] = (flow / cap) if cap > 0 else 0.0
            self.publish_state("flow_update")
            return {"ok": True, "state": self.state.value, "payload": self.payload}
        return super().apply_command(command)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run road device")
    p.add_argument("--device-id", required=True)
    p.add_argument("--district-id", required=True)
    p.add_argument("--intersection-id", default="segment")
    p.add_argument("--broker-host", default="localhost")
    p.add_argument("--broker-port", type=int, default=1883)
    args = p.parse_args(argv)
    dev = RoadDevice(DeviceConfig(args.device_id, DeviceType.ROAD.value, args.district_id, args.intersection_id, args.broker_host, args.broker_port))
    dev.start()
    try:
        while True:
            import time; time.sleep(1)
    except KeyboardInterrupt:
        dev.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

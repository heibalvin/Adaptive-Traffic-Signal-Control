"""Absorber device: sink stub consuming traffic volume."""

from __future__ import annotations

import argparse
from typing import Any

from .base import BaseDevice, DeviceConfig
from ..Common.mqtt import DeviceState, DeviceType


class AbsorberDevice(BaseDevice):
    def __init__(self, config: DeviceConfig):
        super().__init__(
            config,
            initial_payload={
                "capacity_per_min": 0.0,
                "attraction_profile": [0.0] * 1440,
                "current_minute": 0,
                "absorbed_volume": 0.0,
                "queue_volume": 0.0,
                "enabled": False,
            },
        )

    def apply_command(self, command: dict[str, Any]) -> dict[str, Any]:
        params = command.get("params") or {}
        if "attraction_profile" in params and isinstance(params["attraction_profile"], list):
            prof = [max(0.0, min(100.0, float(x))) for x in params["attraction_profile"][:1440]]
            if len(prof) < 1440:
                prof += [0.0] * (1440 - len(prof))
            params["attraction_profile"] = prof
        if "capacity_per_min" in params:
            params["capacity_per_min"] = max(0.0, float(params["capacity_per_min"]))
        action = str(command.get("action", "")).lower()
        if action == "ingest":
            inflow = max(0.0, float(params.get("volume", 0.0)))
            cap = float(self.payload.get("capacity_per_min", 0.0))
            absorbed = min(inflow, cap)
            overflow = max(0.0, inflow - absorbed)
            self.payload["absorbed_volume"] = float(self.payload.get("absorbed_volume", 0.0)) + absorbed
            self.payload["queue_volume"] = max(0.0, float(self.payload.get("queue_volume", 0.0)) + overflow)
            self.payload["last_ingest"] = {"inflow": inflow, "absorbed": absorbed, "overflow": overflow}
            self.publish_state("ingest")
            return {"ok": True, "state": self.state.value, "payload": self.payload}
        if action == "tick":
            minute = int(params.get("minute", self.payload.get("current_minute", 0))) % 1440
            self.payload["current_minute"] = minute
            self.payload["enabled"] = self.state == DeviceState.ACTIVE
            self.publish_state("tick")
            return {"ok": True, "state": self.state.value, "payload": self.payload}
        return super().apply_command(command)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run absorber device")
    p.add_argument("--device-id", required=True)
    p.add_argument("--district-id", required=True)
    p.add_argument("--intersection-id", default="boundary")
    p.add_argument("--broker-host", default="localhost")
    p.add_argument("--broker-port", type=int, default=1883)
    args = p.parse_args(argv)
    dev = AbsorberDevice(DeviceConfig(args.device_id, DeviceType.ABSORBER.value, args.district_id, args.intersection_id, args.broker_host, args.broker_port))
    dev.start()
    try:
        while True:
            import time; time.sleep(1)
    except KeyboardInterrupt:
        dev.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

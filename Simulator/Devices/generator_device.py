"""Generator device: source stub emitting traffic volume."""

from __future__ import annotations

import argparse
from typing import Any

from .base import BaseDevice, DeviceConfig
from ..Common.mqtt import DeviceState, DeviceType


class GeneratorDevice(BaseDevice):
    def __init__(self, config: DeviceConfig):
        super().__init__(
            config,
            initial_payload={
                "rate_per_min": 0.0,
                "probability_profile": [0.0] * 1440,
                "current_minute": 0,
                "generated_volume": 0.0,
                "enabled": False,
            },
        )

    def apply_command(self, command: dict[str, Any]) -> dict[str, Any]:
        params = command.get("params") or {}
        if "probability_profile" in params and isinstance(params["probability_profile"], list):
            prof = [max(0.0, min(100.0, float(x))) for x in params["probability_profile"][:1440]]
            if len(prof) < 1440:
                prof += [0.0] * (1440 - len(prof))
            params["probability_profile"] = prof
        if "rate_per_min" in params:
            params["rate_per_min"] = max(0.0, float(params["rate_per_min"]))
        if str(command.get("action", "")).lower() == "tick":
            minute = int(params.get("minute", self.payload.get("current_minute", 0))) % 1440
            profile = self.payload.get("probability_profile") or [0.0] * 1440
            rate = float(self.payload.get("rate_per_min", 0.0)) * (float(profile[minute]) / 100.0)
            self.payload["current_minute"] = minute
            self.payload["generated_volume"] = float(self.payload.get("generated_volume", 0.0)) + rate
            self.payload["last_emission"] = rate
            self.payload["enabled"] = self.state == DeviceState.ACTIVE
            self.publish_state("tick")
            return {"ok": True, "state": self.state.value, "payload": self.payload}
        return super().apply_command(command)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run generator device")
    p.add_argument("--device-id", required=True)
    p.add_argument("--district-id", required=True)
    p.add_argument("--intersection-id", default="boundary")
    p.add_argument("--broker-host", default="localhost")
    p.add_argument("--broker-port", type=int, default=1883)
    args = p.parse_args(argv)
    dev = GeneratorDevice(DeviceConfig(args.device_id, DeviceType.GENERATOR.value, args.district_id, args.intersection_id, args.broker_host, args.broker_port))
    dev.start()
    try:
        while True:
            import time; time.sleep(1)
    except KeyboardInterrupt:
        dev.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

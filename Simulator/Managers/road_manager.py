"""Road manager."""

from __future__ import annotations

import argparse

from .base import BaseManager
from ..Common.mqtt import DeviceType


class RoadManager(BaseManager):
    def __init__(self, **kwargs):
        super().__init__(device_type=DeviceType.ROAD.value, **kwargs)

    def set_flow(self, district_id: str, intersection_id: str, device_id: str, **params):
        self.send_command(district_id, intersection_id, device_id, "flow_update", params)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run road manager")
    p.add_argument("--broker-host", default="localhost")
    p.add_argument("--broker-port", type=int, default=1883)
    p.add_argument("--district-id", default="+")
    args = p.parse_args(argv)
    mgr = RoadManager(broker_host=args.broker_host, broker_port=args.broker_port, district_id=args.district_id)
    mgr.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mgr.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

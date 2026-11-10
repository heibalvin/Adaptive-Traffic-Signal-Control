"""Viewer application scaffold.

Sprint 1 target: render canvas sprites aligned over the layout image using
topology/state data. This module provides a CLI entry point and state-loading
stub until the UI runtime (e.g., web canvas or desktop canvas) is selected.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ATCS topology viewer")
    p.add_argument("--topology-json", type=Path, required=True, help="Topology JSON file")
    p.add_argument("--layout-image", type=Path, default=None, help="Layout background image")
    p.add_argument("--state-snapshot-url", default=None, help="Controller /api/v1/state/snapshot URL")
    return p


def load_topology(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    topology = load_topology(args.topology_json)
    district = topology.get("district", {})
    counts = {
        "intersections": len(topology.get("intersections", [])),
        "roads": len(topology.get("roads", [])),
        "lights": len(topology.get("lights", [])),
        "detectors": len(topology.get("detectors", [])),
        "generators": len(topology.get("generators", [])),
        "absorbers": len(topology.get("absorbers", [])),
    }
    print(f"topology: {district.get('name', '?')}, {district.get('country', '?')}")
    print(f"layout image: {args.layout_image or '(none)'}")
    print(f"state snapshot URL: {args.state_snapshot_url or '(none; using static topology)'}")
    print("entities: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    print("viewer scaffold ready; canvas sprite rendering not yet implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

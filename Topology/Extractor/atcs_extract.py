"""ATCS Topology Extraction (Sprint 1).

Extracts spatial road network geometry from district/country inputs to a
topology JSON file and generates a layout background image map for the
ATCS Topology Viewer.

Usage:
    python -m Topology.Extractor --district "Downtown Dubai" --country "UAE"

Outputs (default):
    Topology/Data/<country>-<district>-topology.json
    Topology/Data/<country>-<district>-topology.png
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class District:
    id: str
    name: str
    country: str


@dataclass
class Intersection:
    id: str
    district_id: str
    name: str
    x: float
    y: float
    road_ids: list[str] = field(default_factory=list)
    light_ids: list[str] = field(default_factory=list)
    detector_ids: list[str] = field(default_factory=list)


@dataclass
class Road:
    id: str
    district_id: str
    from_intersection_id: str
    to_intersection_id: str
    name: str = ""
    capacity: float | None = None
    speed_limit: float | None = None
    geometry: list[list[float]] = field(default_factory=list)  # [[x, y], ...]


@dataclass
class Light:
    id: str
    intersection_id: str
    phase: str = "red"  # green|yellow|red
    timing_seconds: dict[str, int] = field(default_factory=dict)


@dataclass
class Detector:
    id: str
    intersection_id: str
    road_id: str | None = None
    kind: str = "flow"  # flow|queue


@dataclass
class Topology:
    generated_at: str
    district: District
    intersections: list[Intersection] = field(default_factory=list)
    roads: list[Road] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)
    detectors: list[Detector] = field(default_factory=list)
    generators: list[dict[str, Any]] = field(default_factory=list)
    absorbers: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ATCS spatial topology extraction")
    p.add_argument("--district", required=True, help="District name")
    p.add_argument("--country", required=True, help="Country name")
    p.add_argument("--district-id", default=None, help="Stable district ID override")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("Topology/Data"),
        help="Output directory for default naming (default: Topology/Data)",
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Output topology JSON path (default: <out-dir>/<country>-<district>-topology.json)",
    )
    p.add_argument(
        "--out-image",
        type=Path,
        default=None,
        help="Output layout image path (default: <out-dir>/<country>-<district>-topology.png)",
    )
    return p


def slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def default_output_base(country: str, district: str, out_dir: Path) -> Path:
    return out_dir / f"{slug(country)}-{slug(district)}-topology"


def extract_topology(district: str, country: str, district_id: str | None = None) -> Topology:
    """Extract topology from spatial sources.

    Sprint 1 scaffold: returns a valid, empty topology document with district
    metadata. GeoPandas/OSM extraction is the next implementation step.
    """
    did = district_id or slug(f"{district}-{country}")
    return Topology(
        generated_at=datetime.now(timezone.utc).isoformat(),
        district=District(id=did, name=district, country=country),
        metadata={
            "source": "scaffold",
            "note": "Replace with GeoPandas/OSM extraction in Sprint 1 implementation.",
        },
    )


def write_topology_json(topology: Topology, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(topology), indent=2) + "\n", encoding="utf-8")


def write_layout_image_placeholder(topology: Topology, path: Path) -> Path:
    """Write a layout image placeholder.

    Sprint 1 scaffold: writes a small text marker next to the intended image
    path when image rendering deps are not installed. Replace with real
    map/canvas rendering.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = path.with_suffix(path.suffix + ".txt")
    marker.write_text(
        f"Layout image placeholder for {topology.district.name}, {topology.district.country}\n"
        f"Generated: {topology.generated_at}\n"
        f"Intended image: {path}\n",
        encoding="utf-8",
    )
    return marker


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base = default_output_base(args.country, args.district, args.out_dir)
    out_json = args.out_json or base.with_suffix(".json")
    out_image = args.out_image or base.with_suffix(".png")
    topology = extract_topology(args.district, args.country, args.district_id)
    write_topology_json(topology, out_json)
    marker = write_layout_image_placeholder(topology, out_image)
    print(f"wrote topology JSON: {out_json}")
    print(f"wrote layout image placeholder marker: {marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

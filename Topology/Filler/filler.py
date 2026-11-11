"""Topology Filler: add generator and absorber stubs to existing topology.

Reads a topology JSON/PNG pair (e.g. <country3>-<town>-<district>-topology.json/png)
and produces <country3>-<town>-<district>-topology-filler.json/png with generator
and absorber stub entries added along boundary edges/intersections.

Country should use a 3-letter ISO-like code (e.g. uae, usa, gbr).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_COUNTRY3_ALIASES = {
    "united-arab-emirates": "uae",
    "are": "uae",
    "ae": "uae",
    "united-states": "usa",
    "united-states-of-america": "usa",
    "us": "usa",
    "united-kingdom": "gbr",
    "uk": "gbr",
    "gb": "gbr",
}


def _slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def country_code3(value: str) -> str:
    s = _slug(value)
    if s in _COUNTRY3_ALIASES:
        return _COUNTRY3_ALIASES[s]
    if len(s) == 3 and s.isalpha():
        return s
    return s[:3] if len(s) >= 3 and s.replace("-", "").isalpha() else s


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Add generator/absorber stubs to topology")
    p.add_argument("--country", required=True, help="Country 3-letter code (e.g. uae) or name")
    p.add_argument("--town", default="")
    p.add_argument("--district", required=True)
    p.add_argument("--in-json", type=Path, default=None)
    p.add_argument("--in-png", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=Path("Topology/Data"))
    return p


def default_base(country: str, town: str, district: str, out_dir: Path) -> Path:
    cc = country_code3(country)
    if town:
        return out_dir / f"{cc}-{_slug(town)}-{_slug(district)}-topology-filler"
    return out_dir / f"{cc}-{_slug(district)}-topology-filler"


def filler_name(country: str, town: str, district: str) -> str:
    cc = country_code3(country)
    if town:
        return f"{cc}-{_slug(town)}-{_slug(district)}-topology-filler"
    return f"{cc}-{_slug(district)}-topology-filler"


def _input_candidates(country: str, town: str, district: str, out_dir: Path) -> list[Path]:
    cc = country_code3(country)
    cs = _slug(country)
    names = []
    if town:
        names.extend([
            f"{cc}-{_slug(town)}-{_slug(district)}-topology.json",
            f"{cs}-{_slug(town)}-{_slug(district)}-topology.json",
        ])
    else:
        names.extend([
            f"{cc}-{_slug(district)}-topology.json",
            f"{cs}-{_slug(district)}-topology.json",
        ])
    out: list[Path] = []
    seen: set[str] = set()
    for n in names:
        p = out_dir / n
        if p.as_posix() not in seen:
            seen.add(p.as_posix())
            out.append(p)
    return out


def fill_topology(data: dict[str, Any], country: str, town: str, district: str) -> dict[str, Any]:
    out = dict(data)
    district_id = out.get("district", {}).get("id") or _slug(f"{district}-{town}-{country_code3(country)}")
    out["district"] = {"id": district_id, "name": district, "country": country_code3(country), "town": town or None}
    out["generators"] = out.get("generators") or [
        {
            "id": f"gen-{district_id}-boundary-1",
            "type": "generator",
            "district_id": district_id,
            "location": "boundary",
            "state": "idle",
            "rate_per_min": 0.0,
            "probability_profile": [0.0] * 1440,
            "mqtt": {"telemetry": f"devices/{district_id}/boundary/generator/gen-{district_id}-boundary-1/telemetry", "command": f"devices/{district_id}/boundary/generator/gen-{district_id}-boundary-1/command"},
        }
    ]
    out["absorbers"] = out.get("absorbers") or [
        {
            "id": f"abs-{district_id}-boundary-1",
            "type": "absorber",
            "district_id": district_id,
            "location": "boundary",
            "state": "idle",
            "capacity_per_min": 0.0,
            "attraction_profile": [0.0] * 1440,
            "mqtt": {"telemetry": f"devices/{district_id}/boundary/absorber/abs-{district_id}-boundary-1/telemetry", "command": f"devices/{district_id}/boundary/absorber/abs-{district_id}-boundary-1/command"},
        }
    ]
    out["stubs"] = {"generators": out["generators"], "absorbers": out["absorbers"]}
    out["metadata"] = out.get("metadata") or {}
    out["metadata"]["filler"] = {
        "added_at": datetime.now(timezone.utc).isoformat(),
        "name": filler_name(country, town, district),
        "source": "Topology.Filler",
    }
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_out = default_base(args.country, args.town, args.district, args.out_dir)
    base_out.parent.mkdir(parents=True, exist_ok=True)
    in_json = args.in_json
    if in_json is None:
        candidates = _input_candidates(args.country, args.town, args.district, args.out_dir)
        in_json = next((p for p in candidates if p.exists()), candidates[0])
    if not Path(in_json).exists():
        raise FileNotFoundError(f"input topology JSON not found: {in_json}")
    data = json.loads(Path(in_json).read_text(encoding="utf-8"))
    filled = fill_topology(data, args.country, args.town, args.district)
    out_json = base_out.with_suffix(".json")
    out_json.write_text(json.dumps(filled, indent=2) + "\n", encoding="utf-8")
    if args.in_png and Path(args.in_png).exists():
        import shutil
        shutil.copy2(Path(args.in_png), base_out.with_suffix(".png"))
    else:
        marker = base_out.with_suffix(".png.txt")
        marker.write_text(f"Filler layout marker for {args.district}, {args.town or ''} {args.country}\n", encoding="utf-8")
    print(f"wrote filler topology JSON: {out_json}")
    print(f"wrote filler PNG/marker: {base_out.with_suffix('.png')} or {base_out.with_suffix('.png.txt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

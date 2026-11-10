"""FastAPI web viewer for ATCS topology.

Serves a 3-panel UI and proxies location/extraction requests to the extractor API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import json

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

EXTRACTOR_URL = os.getenv("ATCS_EXTRACTOR_URL", "http://localhost:8010").rstrip("/")
DEFAULT_COUNTRY = os.getenv("ATCS_DEFAULT_COUNTRY", "United Arab Emirates")
DEFAULT_CITY = os.getenv("ATCS_DEFAULT_CITY", "Dubai")
DEFAULT_DISTRICT = os.getenv("ATCS_DEFAULT_DISTRICT", "Downtown Dubai")
DATA_DIR = Path(os.getenv("ATCS_TOPOLOGY_DATA_DIR", "/app/Topology/Data"))
STATIC_DATA_DIR = Path(__file__).resolve().parents[1] / "Data"

app = FastAPI(title="ATCS Topology Viewer", version="0.1.0")
STATIC = Path(__file__).with_name("static")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _proxy(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{EXTRACTOR_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=kwargs.pop("timeout", 120), **kwargs)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"extractor unavailable ({url}): {exc}") from exc
    if resp.status_code >= 400:
        detail = resp.text
        try:
            detail = resp.json()
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)
    try:
        return resp.json()
    except Exception:
        return JSONResponse(content={"raw": resp.text})


def _slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def _static_candidates(payload: dict[str, Any]) -> list[Path]:
    country = _slug(str(payload.get("country") or ""))
    city = _slug(str(payload.get("city") or ""))
    district = _slug(str(payload.get("district") or ""))
    names: list[str] = []
    if country and city and district:
        if country == "united-arab-emirates":
            names.append(f"uae-{city}-{district}-topology.json")
        names.extend([
            f"{country}-{city}-{district}-topology.json",
            f"uae-{city}-{district}-topology.json",
        ])
    out: list[Path] = []
    seen: set[str] = set()
    for base in (DATA_DIR, STATIC_DATA_DIR):
        for name in names:
            p = base / name
            key = p.as_posix()
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def _load_static(payload: dict[str, Any]) -> dict[str, Any] | None:
    fallback: dict[str, Any] | None = None
    for path in _static_candidates(payload):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        district = data.get("district") or {
            "name": payload.get("district"),
            "country": payload.get("country"),
            "city": payload.get("city"),
        }
        geojson = data.get("geojson")
        if not isinstance(geojson, dict) or not any((geojson.get(k) or {}).get("features") for k in ("roads", "intersections", "lights")):
            geojson = {
                "roads": {"type": "FeatureCollection", "features": []},
                "intersections": {"type": "FeatureCollection", "features": []},
                "lights": {"type": "FeatureCollection", "features": []},
            }
        topology = dict(data)
        topology.setdefault("district", district)
        topology.setdefault("roads", topology.get("roads", []))
        topology.setdefault("intersections", topology.get("intersections", []))
        topology.setdefault("lights", topology.get("lights", []))
        topology.setdefault("detectors", topology.get("detectors", []))
        counts = data.get("counts") or {
            "roads": len(geojson.get("roads", {}).get("features", []) or topology.get("roads", []) or []),
            "intersections": len(geojson.get("intersections", {}).get("features", []) or topology.get("intersections", []) or []),
            "lights": len(geojson.get("lights", {}).get("features", []) or topology.get("lights", []) or []),
            "detectors": len(topology.get("detectors", []) or []),
        }
        result = {
            "district": district,
            "counts": counts,
            "files": {"topology_json": str(path), "layout_image": str(path.with_suffix('.png')), "layout_image_marker": None},
            "geojson": geojson,
            "topology": topology,
            "source": "static",
        }
        if data.get("source") == "static" or any((geojson.get(k) or {}).get("features") for k in ("roads", "intersections", "lights")):
            return result
        fallback = fallback or result
    return fallback


@app.get("/")
def index() -> FileResponse:
    path = STATIC / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="viewer UI not found")
    return FileResponse(path)


@app.get("/api/config")
def config() -> dict[str, str]:
    return {
        "extractor_url": EXTRACTOR_URL,
        "default_country": DEFAULT_COUNTRY,
        "default_city": DEFAULT_CITY,
        "default_district": DEFAULT_DISTRICT,
    }


@app.get("/api/countries")
def countries(query: str = "", limit: int = 20, lang: str = "en") -> Any:
    return _proxy("GET", "/countries", params={"query": query, "limit": limit, "lang": lang}, timeout=60)


@app.get("/api/cities")
def cities(country: str = Query(...), query: str = "", limit: int = 30, lang: str = "en") -> Any:
    return _proxy(
        "GET", "/cities", params={"country": country, "query": query, "limit": limit, "lang": lang}, timeout=90
    )


@app.get("/api/districts")
def districts(country: str = Query(...), city: str = "", query: str = "", limit: int = 50, lang: str = "en") -> Any:
    return _proxy(
        "GET",
        "/districts",
        params={"country": country, "city": city, "query": query, "limit": limit, "lang": lang, "source": "nominatim"},
        timeout=120,
    )


@app.post("/api/extract")
def extract(payload: dict[str, Any]) -> Any:
    payload.setdefault("mode", "geopandas")
    payload.setdefault("write_files", False)
    payload.setdefault("include_geojson", True)
    payload.setdefault("include_topology", True)

    static = _load_static(payload)
    if static is not None:
        return static

    return _proxy("POST", "/extract", json=payload, timeout=300)

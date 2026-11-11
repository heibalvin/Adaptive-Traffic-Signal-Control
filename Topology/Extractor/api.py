"""FastAPI service for ATCS topology extraction.

Endpoints:
- GET /health
- GET /countries
- GET /cities?country=...
- GET /districts?country=...&city=...
- POST /extract (GeoPandas/OSM extraction for roads/intersections/lights)
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .atcs_extract import default_output_base, extract_topology, write_layout_image_placeholder, write_topology_json
from .gather_district_names import gather_district_names
from .location_api import list_cities, list_countries, list_districts

app = FastAPI(
    title="ATCS Topology Extractor API",
    version="0.2.0",
    description="Granular location discovery and GeoPandas/OSM topology extraction for ATCS.",
)

DATA_DIR = Path(os.getenv("ATCS_TOPOLOGY_DATA_DIR", "Topology/Data"))


class ExtractRequest(BaseModel):
    country: str = Field(..., description="Country name or ISO code")
    district: str = Field(..., description="District/suburb/locality name")
    city: str = Field("", description="Optional city/municipality for place disambiguation")
    district_id: str | None = Field(None, description="Optional stable district ID")
    network_type: str = Field("drive", description="OSMnx network type: drive, walk, bike, all, etc.")
    write_files: bool = Field(True, description="Write topology JSON and layout placeholder to data dir")
    include_geojson: bool = Field(True, description="Include GeoJSON layers for roads/intersections/lights")
    include_topology: bool = Field(True, description="Include ATCS domain topology payload")
    mode: Literal["geopandas", "scaffold"] = Field(
        "geopandas",
        description="geopandas uses OSMnx/GeoPandas; scaffold returns metadata-only topology",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "atcs-topology-extractor"}


@app.get("/countries")
def countries(
    query: str = Query("", description="Optional country name filter"),
    limit: int = Query(50, ge=1, le=100),
    timeout: int = Query(30, ge=5, le=120),
    lang: str = Query("en", description="Preferred name language"),
) -> dict[str, Any]:
    try:
        items = list_countries(query=query, limit=limit, timeout=timeout, lang=lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"country discovery failed: {exc}") from exc
    return {"query": query, "count": len(items), "countries": items}


@app.get("/cities")
def cities(
    country: str = Query(..., description="Country name or ISO alpha-2 code"),
    query: str = Query("", description="Optional city name filter"),
    limit: int = Query(50, ge=1, le=100),
    timeout: int = Query(30, ge=5, le=120),
    lang: str = Query("en", description="Preferred name language"),
) -> dict[str, Any]:
    try:
        items = list_cities(country=country, query=query, limit=limit, timeout=timeout, lang=lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"city discovery failed: {exc}") from exc
    return {"country": country, "query": query, "count": len(items), "cities": items}


@app.get("/districts")
def districts(
    country: str = Query(..., description="Country name or ISO alpha-2 code"),
    city: str = Query("", description="City/municipality"),
    query: str = Query("", description="Optional district name filter"),
    source: Literal["nominatim", "overpass", "both"] = Query("nominatim"),
    limit: int = Query(50, ge=1, le=200),
    timeout: int = Query(60, ge=5, le=180),
    lang: str = Query("en", description="Preferred name language"),
) -> dict[str, Any]:
    try:
        if query or not city:
            items = list_districts(country=country, city=city, query=query, limit=limit, timeout=timeout, lang=lang)
            return {
                "country": country,
                "city": city,
                "query": query,
                "source": "nominatim-search",
                "count": len(items),
                "districts": items,
            }
        items = gather_district_names(
            country=country,
            city=city,
            source=source,
            limit=limit,
            timeout=timeout,
            lang=lang,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"district discovery failed: {exc}") from exc
    return {
        "country": country,
        "city": city,
        "query": query,
        "source": source,
        "count": len(items),
        "districts": [asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in items],
    }


@app.post("/extract")
def extract(req: ExtractRequest) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from .atcs_extract import country_code3, slug as _slug
    country = country_code3(req.country)
    city = _slug(req.city) if req.city else ""
    district = _slug(req.district)
    parts = [p for p in (country, city, district) if p]
    base = DATA_DIR / ("-".join(parts) + "-topology")
    out_json = base.with_suffix(".json")
    out_image = base.with_suffix(".png")

    if req.mode == "scaffold":
        topology = extract_topology(req.district, req.country, req.district_id)
        layers = {
            "roads": {"type": "FeatureCollection", "features": []},
            "intersections": {"type": "FeatureCollection", "features": []},
            "lights": {"type": "FeatureCollection", "features": []},
        }
    else:
        try:
            from .geopandas_extract import extract_geopandas_data
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"GeoPandas dependencies unavailable: {exc}") from exc
        try:
            topology, layers = extract_geopandas_data(
                country=req.country,
                district=req.district,
                city=req.city,
                network_type=req.network_type,
                district_id=req.district_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"GeoPandas extraction failed: {exc}") from exc

    marker = None
    if req.write_files:
        write_topology_json(topology, out_json)
        marker = str(write_layout_image_placeholder(topology, out_image))

    result: dict[str, Any] = {
        "district": asdict(topology.district),
        "generated_at": topology.generated_at,
        "files": {
            "topology_json": str(out_json) if req.write_files else None,
            "layout_image_marker": marker,
            "layout_image": str(out_image) if req.write_files else None,
        },
        "counts": {
            "roads": len(topology.roads),
            "intersections": len(topology.intersections),
            "lights": len(topology.lights),
            "detectors": len(topology.detectors),
        },
    }
    if req.include_topology:
        result["topology"] = asdict(topology)
    if req.include_geojson:
        result["geojson"] = layers
    return result

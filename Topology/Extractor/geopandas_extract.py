"""GeoPandas/OSM topology extraction for ATCS districts.

Extracts road, intersection, and traffic-light features for a district using
OSMnx/GeoPandas and maps them into the ATCS domain model.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .atcs_extract import Detector, District, Intersection, Light, Road, Topology, slug


def _place_query(country: str, district: str, city: str = "") -> str:
    parts = [p for p in (district, city, country) if p and p.strip()]
    return ", ".join(parts)


def _float_attr(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        if isinstance(value, (list, tuple, set)):
            value = next(iter(value), None)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _str_attr(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple, set)):
        value = next((v for v in value if v is not None), default)
    return str(value)


def _line_coords(geom: Any) -> list[list[float]]:
    if geom is None or geom.is_empty:
        return []
    try:
        return [[float(x), float(y)] for x, y in geom.coords]
    except Exception:
        return []


def _point_xy(geom: Any) -> tuple[float, float] | None:
    if geom is None or geom.is_empty:
        return None
    try:
        return float(geom.x), float(geom.y)
    except Exception:
        return None


def extract_geopandas_data(
    country: str,
    district: str,
    city: str = "",
    network_type: str = "drive",
    district_id: str | None = None,
) -> tuple[Topology, dict[str, Any]]:
    """Extract OSM data and return (Topology, geopandas_geojson_layers).

    GeoJSON layers are FeatureCollections for roads, intersections, and lights.
    OSMnx network calls require internet access in the runtime environment.
    """
    try:
        import geopandas as gpd  # noqa: F401
        import osmnx as ox
    except Exception as exc:  # pragma: no cover - depends on runtime deps
        raise RuntimeError(
            "GeoPandas extraction requires geopandas and osmnx to be installed"
        ) from exc

    place = _place_query(country, district, city)
    did = district_id or slug(f"{district}-{city}-{country}" if city else f"{district}-{country}")
    topology = Topology(
        generated_at=datetime.now(timezone.utc).isoformat(),
        district=District(id=did, name=district, country=country),
        metadata={"source": "osmnx", "place_query": place, "network_type": network_type},
    )

    try:
        graph = ox.graph_from_place(place, network_type=network_type, simplify=True)
    except Exception as exc:
        topology.metadata.update({"error": str(exc), "status": "place_not_found_or_unavailable"})
        empty = {"type": "FeatureCollection", "features": []}
        return topology, {"roads": empty, "intersections": empty, "lights": empty}

    nodes_gdf, edges_gdf = ox.graph_to_gdfs(graph, nodes=True, edges=True, fill_edge_geometry=True)
    try:
        nodes_gdf = ox.project_gdf(nodes_gdf)
        edges_gdf = ox.project_gdf(edges_gdf)
    except Exception:
        pass

    nodes_wgs = nodes_gdf.to_crs(4326) if getattr(nodes_gdf, "crs", None) else nodes_gdf
    edges_wgs = edges_gdf.to_crs(4326) if getattr(edges_gdf, "crs", None) else edges_gdf

    node_id_map: dict[Any, str] = {}
    for idx, row in nodes_wgs.iterrows():
        osmid = row.get("osmid", idx)
        nid = f"int-{osmid}"
        node_id_map[osmid] = nid
        xy = _point_xy(row.geometry)
        x, y = (xy if xy else (0.0, 0.0))
        highway = row.get("highway")
        is_signal = highway == "traffic_signals" or (
            isinstance(highway, (list, tuple, set)) and "traffic_signals" in highway
        )
        topology.intersections.append(
            Intersection(
                id=nid,
                district_id=did,
                name=_str_attr(row.get("name") or row.get("ref") or osmid),
                x=x,
                y=y,
            )
        )
        if is_signal:
            topology.lights.append(
                Light(id=f"light-{osmid}", intersection_id=nid, phase="red", timing_seconds={})
            )

    for idx, row in edges_wgs.iterrows():
        osmid = row.get("osmid", idx)
        u = row.get("u") if "u" in row.index else (idx[0] if isinstance(idx, tuple) else None)
        v = row.get("v") if "v" in row.index else (idx[1] if isinstance(idx, tuple) else None)
        key = row.get("key") if "key" in row.index else (idx[2] if isinstance(idx, tuple) else 0)
        from_id = node_id_map.get(u, f"int-{u}")
        to_id = node_id_map.get(v, f"int-{v}")
        rid = f"road-{osmid}-{key}" if osmid is not None else f"road-{u}-{v}-{key}"
        road = Road(
            id=rid,
            district_id=did,
            from_intersection_id=from_id,
            to_intersection_id=to_id,
            name=_str_attr(row.get("name")),
            capacity=_float_attr(row.get("lanes")),
            speed_limit=_float_attr(row.get("maxspeed")),
            geometry=_line_coords(row.geometry),
        )
        topology.roads.append(road)
        for nid in (from_id, to_id):
            for inter in topology.intersections:
                if inter.id == nid and rid not in inter.road_ids:
                    inter.road_ids.append(rid)
                    break

    for light in topology.lights:
        for inter in topology.intersections:
            if inter.id == light.intersection_id and light.id not in inter.light_ids:
                inter.light_ids.append(light.id)
                break

    topology.metadata["counts"] = {
        "intersections": len(topology.intersections),
        "roads": len(topology.roads),
        "lights": len(topology.lights),
    }

    layers = {
        "roads": json_safe_geojson(edges_wgs, ["osmid", "name", "highway", "lanes", "maxspeed", "oneway"]),
        "intersections": json_safe_geojson(nodes_wgs, ["osmid", "name", "highway", "street_count", "junction"]),
        "lights": json_safe_geojson(
            nodes_wgs[nodes_wgs.apply(_is_signal_row, axis=1)] if len(nodes_wgs) else nodes_wgs,
            ["osmid", "name", "highway"],
        ),
    }
    return topology, layers


def _is_signal_row(row: Any) -> bool:
    highway = row.get("highway")
    return highway == "traffic_signals" or (
        isinstance(highway, (list, tuple, set)) and "traffic_signals" in highway
    )


def json_safe_geojson(gdf: Any, keep_cols: list[str] | None = None) -> dict[str, Any]:
    if gdf is None or len(gdf) == 0:
        return {"type": "FeatureCollection", "features": []}
    cols = [c for c in (keep_cols or []) if c in gdf.columns]
    cols = [*cols, gdf.geometry.name]
    slim = gdf[cols].copy()
    for col in slim.columns:
        if col == slim.geometry.name:
            continue
        slim[col] = slim[col].map(_json_value)
    try:
        if slim.crs and str(slim.crs) != "EPSG:4326":
            slim = slim.to_crs(4326)
    except Exception:
        pass
    import json

    return json.loads(slim.to_json())


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_value(v) for v in value]
    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass
    return str(value)

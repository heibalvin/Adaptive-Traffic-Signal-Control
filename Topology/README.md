# ATCS Topology (Sprint 1)

`feature/atcs-topology-generator` — App 1: Urban spatial network extraction and visual topology rendering.

## Scope (DESIGN.md Sprint 1)

1. **`Topology/Extractor/`** — FastAPI service + CLI for granular location discovery (country/city/district) and spatial extraction. Produces topology JSON and GeoJSON layers for roads, intersections, and traffic lights.
2. **`Topology/Viewer/`** — Dockerized web viewer (3-panel UI) that proxies extractor APIs, defaults to UAE/Dubai/Downtown Dubai, and renders district map + selectable road/light/intersection details.

## Structure

```text
Topology/
  README.md
  __init__.py
  docker-compose.yml           # Compose project: atcs (extractor + viewer)
  Extractor/
    __init__.py
    __main__.py
    api.py                     # FastAPI REST API
    atcs_extract.py            # CLI extractor / topology file naming
    gather_district_names.py   # District name helper (CLI)
    geopandas_extract.py       # OSMnx/GeoPandas extraction (roads/intersections/lights)
    location_api.py            # Country/city/district discovery
    requirements.txt
    Dockerfile                 # python:3.12-slim
  Viewer/
    __init__.py
    __main__.py
    api.py                     # Web UI server + extractor proxy
    app.py                     # CLI scaffold
    requirements.txt
    Dockerfile                 # python:3.12-slim
    static/index.html          # 3-panel web app
  Data/                        # Generated/static topology outputs
    uae-dubai-downtown-topology.json
    uae-dubai-downtown-topology.png (if present)
```

## Deploy (Docker)

From the repository root:

```bash
docker compose -f Topology/docker-compose.yml up --build -d
docker compose -f Topology/docker-compose.yml ps
```

Services (Compose project `atcs`):

| Service | Container | URL | Purpose |
|---|---|---|---|
| `topology-extractor` | `atcs-topology-extractor` | `http://localhost:8010` | REST API for countries/cities/districts + GeoPandas extraction |
| `topology-viewer` | `atcs-topology-viewer` | `http://localhost:8011` | Web UI (proxies extractor API) |

Health checks:

```bash
curl -s http://localhost:8010/health
curl -s http://localhost:8011/api/config
```

Stop:

```bash
docker compose -f Topology/docker-compose.yml down
```

## Static topology data (viewer fast path)

Place static files in `Topology/Data/` (mounted into viewer and extractor containers):

- `Topology/Data/uae-dubai-downtown-topology.json`
- `Topology/Data/uae-dubai-downtown-topology.png` (optional background)

The provided `uae-dubai-downtown-topology.json` includes GeoJSON/counts for Downtown Dubai so the viewer can render quickly. `Viewer /api/extract` checks static topology data in `Topology/Data/` first (matching `country/city/district`, including the `uae-dubai-downtown-topology.json` naming style); if no static file is available for the selected location, it proxies to the extractor (`POST /extract`, GeoPandas/OSM).

## Web app (Viewer)

Open: **http://localhost:8011**

Behavior:
- **Left panel:** choose **Country**, **Town/City**, then **District**. Defaults: `United Arab Emirates` / `Dubai` / `Downtown Dubai`.
- **Load district topology:** loads static data when present; otherwise calls extractor. `scaffold` mode is fast for API/UI checks; `geopandas` performs live OSMnx extraction and may take longer.
- **Center panel:** district map background + foreground entities (`roads`, `intersections`, traffic-signal `lights`). Tabs list Roads/Lights/Intersections.
- **Right panel:** details for the selected road, light, or intersection (selected from map or list).

Viewer config/proxy endpoints:

```bash
curl -s http://localhost:8011/api/config
curl -sG "http://localhost:8011/api/districts" \
  --data-urlencode "country=United Arab Emirates" \
  --data-urlencode "city=Dubai" --data-urlencode "limit=10"
```

## REST API (Extractor)

Base URL: `http://localhost:8010`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/countries?query=uae&lang=en&limit=...` | Country lookup |
| `GET` | `/cities?country=uae&query=dubai&lang=en&limit=...` | Cities in country |
| `GET` | `/districts?country=uae&city=dubai&lang=en&limit=...` | Districts in country/city |
| `POST` | `/extract` | Extract topology (GeoPandas/OSM or scaffold) |

### UAE / Dubai example flow

```bash
# 1) Countries
curl -sG "http://localhost:8010/countries" \
  --data-urlencode "query=uae" --data-urlencode "lang=en" --data-urlencode "limit=5" \
| jq '{count, countries: [.countries[] | {country, country_code}]}'

# 2) Cities in UAE (query Dubai)
curl -sG "http://localhost:8010/cities" \
  --data-urlencode "country=uae" --data-urlencode "query=dubai" \
  --data-urlencode "lang=en" --data-urlencode "limit=10" \
| jq '{country, count, cities: [.cities[] | {city, state, kind}]}'

# 3) Districts in UAE / Dubai
curl -sG "http://localhost:8010/districts" \
  --data-urlencode "country=uae" --data-urlencode "city=dubai" \
  --data-urlencode "source=nominatim" --data-urlencode "lang=en" --data-urlencode "limit=20" \
| jq '{country, city, count, districts: [.districts[] | (.district // .name)]}'
```

UAE/Dubai test result (live OSM-backed responses may vary):

```json
{"query":"uae","count":1,"countries":[{"country":"United Arab Emirates","country_code":"AE"}]}
{"country":"uae","query":"dubai","count":1,"cities":[{"city":"Dubai","state":"Dubai Emirate","kind":"city"}]}
{"country":"uae","city":"dubai","source":"nominatim","count":4,"districts":["Hayl","Shariyah","Sufayri","World Islands"]}
```

### Extract topology for a district

```bash
curl -s -X POST "http://localhost:8010/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "country":"United Arab Emirates",
    "city":"Dubai",
    "district":"Downtown Dubai",
    "mode":"geopandas",
    "network_type":"drive",
    "write_files":true,
    "include_geojson":true,
    "include_topology":false
  }' | jq '{district, counts, files, geojson_feature_counts: {roads:(.geojson.roads.features|length), intersections:(.geojson.intersections.features|length), lights:(.geojson.lights.features|length)}}'
```

`POST /extract` returns ATCS counts (`roads/intersections/lights/detectors`), file paths under `Topology/Data/`, and GeoJSON layers for `roads`, `intersections`, and traffic-signal `lights`. `geopandas` mode needs outbound OSM access and can take time/rate-limit; use `mode:"scaffold"` for fast contract checks.

## CLI helpers

```bash
# District names (English)
python3 -m Topology.Extractor.gather_district_names --country uae --city dubai --format names

# Basic extractor scaffold/file naming
python3 -m Topology.Extractor --district "Downtown Dubai" --country "UAE"
```

## Notes

- Discovery uses OSM/Nominatim (and optional Overpass paths in code); live results can vary.
- Keep extraction, persistence, and rendering concerns separated (device/controller/viewer boundaries from DESIGN.md).
- Align generated JSON with domain entities: Generator, Absorber, Road, Light, Detector, Intersection, District.


"""Gather district/suburb/locality names for a country, city, or town.

Uses OpenStreetMap data sources (Nominatim search and/or Overpass) to list
candidate district names that can be passed to Topology.Extractor.

Usage:
    python -m Topology.Extractor.gather_district_names --country "United Arab Emirates" --city "Dubai"
    python -m Topology.Extractor.gather_district_names --country "AE" --source overpass --limit 100
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

USER_AGENT = "atcs-topology-extractor/0.1 (local dev)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass
class DistrictCandidate:
    name: str
    display_name: str
    country: str
    city: str
    town: str
    kind: str
    source: str
    osm_type: str = ""
    osm_id: str = ""


def _http_get_json(url: str, params: dict[str, str], timeout: int, lang: str = "en") -> Any:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": lang,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, data: dict[str, str], timeout: int, lang: str = "en") -> Any:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": lang,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _place_queries(country: str, city: str = "", town: str = "") -> list[str]:
    parts = [p.strip() for p in (town, city, country) if p and p.strip()]
    where = ", ".join(parts)
    locality = ", ".join([p for p in (town, city) if p and p.strip()])
    if locality:
        return [
            f"districts in {where}",
            f"suburbs in {where}",
            f"neighbourhoods in {where}",
            f"{locality} districts",
        ]
    return [f"districts in {country}", f"suburbs in {country}"]


def _country_code(country: str) -> str | None:
    c = country.strip().upper()
    aliases = {"UAE": "AE", "ARE": "AE", "UK": "GB", "GBR": "GB", "USA": "US"}
    if c in aliases:
        return aliases[c]
    if len(c) == 2 and c.isalpha():
        return c
    return None


def _nominatim_items(query: str, limit: int, timeout: int, lang: str = "en") -> list[dict[str, Any]]:
    payload = _http_get_json(
        NOMINATIM_URL,
        {
            "q": query,
            "format": "jsonv2",
            "addressdetails": "1",
            "accept-language": lang,
            "limit": str(limit),
        },
        timeout=timeout,
        lang=lang,
    )
    return payload if isinstance(payload, list) else []


def _candidate_name(item: dict[str, Any], addr: dict[str, Any]) -> str:
    name = (
        item.get("name")
        or addr.get("suburb")
        or addr.get("quarter")
        or addr.get("neighbourhood")
        or addr.get("city_district")
        or addr.get("district")
        or addr.get("borough")
        or addr.get("hamlet")
        or ""
    )
    if name:
        return str(name)
    display = str(item.get("display_name") or "")
    if display:
        head = display.split(",", 1)[0].strip()
        if head:
            return head
    return ""


def gather_nominatim(
    country: str,
    city: str = "",
    town: str = "",
    limit: int = 50,
    timeout: int = 30,
    lang: str = "en",
) -> list[DistrictCandidate]:
    raw: list[dict[str, Any]] = []
    per_query = max(10, min(limit, 50))
    for query in _place_queries(country, city, town):
        try:
            raw.extend(_nominatim_items(query, per_query, timeout, lang=lang))
        except Exception:
            continue
        if len(raw) >= limit:
            break
    out: list[DistrictCandidate] = []
    for item in raw[: max(limit * 2, limit)]:
        addr = item.get("address") or {}
        name = _candidate_name(item, addr)
        if not name:
            continue
        cls = str(item.get("class") or "")
        typ = str(item.get("type") or "")
        if cls and cls not in {"boundary", "place", "landuse", "highway"} and typ not in {
            "administrative",
            "suburb",
            "quarter",
            "neighbourhood",
            "district",
            "city_district",
            "residential",
        }:
            if not city and not town:
                continue
        out.append(
            DistrictCandidate(
                name=name,
                display_name=str(item.get("display_name") or name),
                country=str(addr.get("country") or country),
                city=str(addr.get("city") or addr.get("municipality") or addr.get("state") or city),
                town=str(addr.get("town") or addr.get("village") or town),
                kind=str(item.get("type") or item.get("category") or "district"),
                source="nominatim",
                osm_type=str(item.get("osm_type") or ""),
                osm_id=str(item.get("osm_id") or ""),
            )
        )
        if len(out) >= limit:
            break
    return _dedupe(out)


def _overpass_area_filter(country: str, city: str = "", town: str = "") -> str:
    code = _country_code(country)
    if code:
        base = f'area["ISO3166-1"="{code}"]["admin_level"="2"]->.country;'
    else:
        country_name = country.replace('"', '\\"')
        base = f'area["name"="{country_name}"]->.country;'
    if city or town:
        locality = (town or city).replace('"', '\\"')
        return base + f'area(area.country)["name"="{locality}"]->.search;'
    return base + ".country->.search;"


def _tag_name(tags: dict[str, Any]) -> str:
    for key in ("name:en", "int_name", "name"):
        value = tags.get(key)
        if value:
            return str(value)
    return ""


def gather_overpass(
    country: str,
    city: str = "",
    town: str = "",
    limit: int = 100,
    timeout: int = 60,
) -> list[DistrictCandidate]:
    area = _overpass_area_filter(country, city, town)
    query = f"""[out:json][timeout:{timeout}];
{area}
(
  rel(area.search)["boundary"="administrative"]["name"]["admin_level"~"^(8|9|10|11)$"];
  node(area.search)["place"~"^(suburb|quarter|neighbourhood|district|city_district)$"]["name"];
  way(area.search)["place"~"^(suburb|quarter|neighbourhood|district|city_district)$"]["name"];
  relation(area.search)["place"~"^(suburb|quarter|neighbourhood|district|city_district)$"]["name"];
);
out tags {limit};"""
    payload = _http_post_json(OVERPASS_URL, {"data": query}, timeout=timeout + 5)
    out: list[DistrictCandidate] = []
    for el in (payload.get("elements") or []) if isinstance(payload, dict) else []:
        tags = el.get("tags") or {}
        name = _tag_name(tags)
        if not name:
            continue
        display = str(tags.get("name:en") or tags.get("official_name:en") or tags.get("official_name") or name)
        out.append(
            DistrictCandidate(
                name=name,
                display_name=display,
                country=str(tags.get("addr:country") or country),
                city=str(tags.get("addr:city") or city),
                town=str(tags.get("addr:town") or town),
                kind=str(tags.get("place") or tags.get("admin_level") or "district"),
                source="overpass",
                osm_type=str(el.get("type") or ""),
                osm_id=str(el.get("id") or ""),
            )
        )
    return _dedupe(out)


def _dedupe(items: list[DistrictCandidate]) -> list[DistrictCandidate]:
    seen: set[tuple[str, str, str]] = set()
    out: list[DistrictCandidate] = []
    for item in items:
        key = (item.name.casefold(), item.city.casefold(), item.kind.casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return sorted(out, key=lambda i: (i.name.casefold(), i.city.casefold()))


def gather_places(
    query: str,
    country: str = "",
    city: str = "",
    district: str = "",
    limit: int = 50,
    timeout: int = 30,
    lang: str = "en",
    place_types: set[str] | None = None,
    classes: set[str] | None = None,
) -> list[DistrictCandidate]:
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "accept-language": lang,
        "limit": str(max(1, min(limit, 100))),
    }
    payload = _http_get_json(NOMINATIM_URL, params, timeout=timeout, lang=lang)
    out: list[DistrictCandidate] = []
    for item in payload if isinstance(payload, list) else []:
        addr = item.get("address") or {}
        name = _candidate_name(item, addr)
        if not name:
            continue
        cls = str(item.get("class") or "")
        typ = str(item.get("type") or "")
        if classes and cls not in classes:
            continue
        if place_types and typ not in place_types:
            continue
        out.append(
            DistrictCandidate(
                name=name,
                display_name=str(item.get("display_name") or name),
                country=str(addr.get("country") or country),
                city=str(
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("municipality")
                    or addr.get("state_district")
                    or city
                ),
                town=str(addr.get("town") or addr.get("village") or ""),
                kind=typ or cls or "place",
                source="nominatim",
                osm_type=str(item.get("osm_type") or ""),
                osm_id=str(item.get("osm_id") or ""),
            )
        )
    return _dedupe(out)


def gather_countries(query: str = "", limit: int = 50, timeout: int = 30, lang: str = "en") -> list[DistrictCandidate]:
    q = query.strip() or "country"
    return gather_places(
        q,
        limit=limit,
        timeout=timeout,
        lang=lang,
        place_types={"country"},
        classes={"boundary", "place"},
    )


def gather_cities(
    country: str,
    query: str = "",
    district: str = "",
    limit: int = 50,
    timeout: int = 30,
    lang: str = "en",
) -> list[DistrictCandidate]:
    parts = [p for p in (query.strip(), district.strip(), country.strip()) if p]
    q = " ".join(parts) if query.strip() or district.strip() else f"cities in {country}"
    return gather_places(
        q,
        country=country,
        district=district,
        limit=limit,
        timeout=timeout,
        lang=lang,
        place_types={"city", "town", "municipality", "administrative"},
        classes={"boundary", "place"},
    )
def gather_district_names(
    country: str,
    city: str = "",
    town: str = "",
    source: str = "nominatim",
    limit: int = 50,
    timeout: int = 60,
    lang: str = "en",
) -> list[DistrictCandidate]:
    if source == "nominatim":
        return gather_nominatim(
            country, city=city, town=town, limit=limit, timeout=min(timeout, 30), lang=lang
        )
    if source == "overpass":
        return gather_overpass(country, city=city, town=town, limit=limit, timeout=timeout)
    if source == "both":
        items = gather_nominatim(
            country, city=city, town=town, limit=limit, timeout=min(timeout, 30), lang=lang
        )
        try:
            items.extend(gather_overpass(country, city=city, town=town, limit=limit, timeout=timeout))
        except Exception as exc:  # network/service variability
            print(f"overpass unavailable, using nominatim results only: {exc}", file=sys.stderr)
        return _dedupe(items)
    raise ValueError(f"unknown source: {source}")



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gather district names per country/city/town")
    p.add_argument("--country", required=True, help="Country name or ISO 3166-1 alpha-2 code")
    p.add_argument("--city", default="", help="City/municipality name (optional)")
    p.add_argument("--town", default="", help="Town/village name (optional)")
    p.add_argument("--source", choices=["nominatim", "overpass", "both"], default="nominatim")
    p.add_argument("--limit", type=int, default=50, help="Maximum results per source")
    p.add_argument("--timeout", type=int, default=60, help="Network timeout seconds")
    p.add_argument("--lang", default="en", help="Preferred output language for names (default: en)")
    p.add_argument("--format", choices=["json", "tsv", "names"], default="json")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    items = gather_district_names(
        country=args.country,
        city=args.city,
        town=args.town,
        source=args.source,
        limit=args.limit,
        timeout=args.timeout,
        lang=args.lang,
    )
    if args.format == "json":
        print(json.dumps([asdict(i) for i in items], indent=2, ensure_ascii=False))
    elif args.format == "tsv":
        print("name\tcity\ttown\tcountry\tkind\tsource\tdisplay_name")
        for i in items:
            print(
                "\t".join([i.name, i.city, i.town, i.country, i.kind, i.source, i.display_name])
            )
    else:
        for i in items:
            print(i.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

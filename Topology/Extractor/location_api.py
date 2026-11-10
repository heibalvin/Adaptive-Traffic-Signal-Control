"""Granular location discovery helpers for ATCS extractor API."""

from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .gather_district_names import (
    NOMINATIM_URL,
    OVERPASS_URL,
    USER_AGENT,
    DistrictCandidate,
    _candidate_name,
    _country_code,
    _dedupe,
    _http_post_json,
)


@dataclass
class PlaceCandidate:
    name: str
    display_name: str
    country: str
    country_code: str
    state: str
    city: str
    district: str
    kind: str
    source: str
    osm_type: str = ""
    osm_id: str = ""


def _get(params: dict[str, str], timeout: int, lang: str) -> Any:
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Language": lang},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        import json

        return json.loads(resp.read().decode("utf-8"))


def _rows(payload: Any) -> list[dict[str, Any]]:
    return payload if isinstance(payload, list) else []


def _candidate(item: dict[str, Any], source: str = "nominatim") -> PlaceCandidate | None:
    addr = item.get("address") or {}
    name = _candidate_name(item, addr)
    if not name:
        return None
    country = str(addr.get("country") or "")
    code = str(addr.get("country_code") or _country_code(country) or "").upper()
    return PlaceCandidate(
        name=name,
        display_name=str(item.get("display_name") or name),
        country=country,
        country_code=code,
        state=str(addr.get("state") or addr.get("province") or addr.get("region") or ""),
        city=str(
            addr.get("city")
            or addr.get("town")
            or addr.get("municipality")
            or addr.get("state_district")
            or ""
        ),
        district=str(
            addr.get("suburb")
            or addr.get("quarter")
            or addr.get("neighbourhood")
            or addr.get("city_district")
            or addr.get("district")
            or ""
        ),
        kind=str(item.get("type") or item.get("category") or "place"),
        source=source,
        osm_type=str(item.get("osm_type") or ""),
        osm_id=str(item.get("osm_id") or ""),
    )


def _search(q: str, limit: int, timeout: int, lang: str, featuretype: str = "") -> list[dict[str, Any]]:
    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": "1",
        "accept-language": lang,
        "limit": str(max(1, min(limit, 100))),
    }
    if featuretype:
        params["featuretype"] = featuretype
    return _rows(_get(params, timeout, lang))


def list_countries(query: str = "", limit: int = 50, timeout: int = 30, lang: str = "en") -> list[dict[str, Any]]:
    raw_q = query.strip()
    aliases = {"uae": "United Arab Emirates", "ae": "United Arab Emirates", "uk": "United Kingdom", "usa": "United States"}
    q = aliases.get(raw_q.lower(), raw_q) or "country"
    items = _search(q, limit=max(limit * 3, 25), timeout=timeout, lang=lang)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        c = _candidate(item)
        if not c:
            continue
        if c.kind != "country" and not (c.kind == "administrative" and c.country and c.display_name.count(",") <= 1):
            continue
        key = c.country_code or (c.country or c.name).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "country": c.country or c.name,
                "country_code": c.country_code or (_country_code(c.country or c.name) or ""),
                "display_name": c.display_name,
                "osm_type": c.osm_type,
                "osm_id": c.osm_id,
                "kind": c.kind,
            }
        )
        if len(out) >= limit:
            break
    if not out and raw_q:
        code = _country_code(raw_q)
        name = aliases.get(raw_q.lower(), raw_q if len(raw_q) > 2 else "")
        if name or code:
            out.append(
                {
                    "country": name or code or raw_q,
                    "country_code": code or "",
                    "display_name": name or raw_q,
                    "osm_type": "",
                    "osm_id": "",
                    "kind": "country",
                }
            )
    return sorted(out, key=lambda x: x["country"])


def list_cities(
    country: str,
    query: str = "",
    limit: int = 50,
    timeout: int = 30,
    lang: str = "en",
) -> list[dict[str, Any]]:
    aliases = {"uae": "United Arab Emirates", "ae": "United Arab Emirates", "uk": "United Kingdom", "usa": "United States"}
    ctry = aliases.get(country.strip().lower(), country)
    code = _country_code(ctry) or _country_code(country)
    allowed = {"city", "town", "municipality"}
    q = f"{query.strip()}, {ctry}" if query.strip() else ctry
    items = _search(q, limit=max(limit * 4, 40), timeout=timeout, lang=lang)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        c = _candidate(item)
        if not c:
            continue
        if c.country_code and code and c.country_code != code:
            continue
        if c.kind in allowed:
            city = c.name
        elif query.strip() and c.city and c.city.casefold() == query.strip().casefold():
            city = c.city
        else:
            continue
        key = city.casefold()
        if not city or key in seen or key == ctry.casefold():
            continue
        seen.add(key)
        out.append(
            {
                "city": city,
                "country": c.country or ctry,
                "country_code": c.country_code or code or "",
                "state": c.state,
                "kind": c.kind if c.kind in allowed else "city",
                "display_name": c.display_name,
                "osm_type": c.osm_type,
                "osm_id": c.osm_id,
            }
        )
        if len(out) >= limit:
            break
    if not out and code == "AE" and not query.strip():
        for city in [
            "Abu Dhabi",
            "Dubai",
            "Sharjah",
            "Ajman",
            "Ras Al Khaimah",
            "Fujairah",
            "Umm Al Quwain",
            "Al Ain",
        ]:
            try:
                for item in _search(f"{city}, United Arab Emirates", limit=5, timeout=timeout, lang=lang):
                    c = _candidate(item)
                    if c and c.name.casefold() == city.casefold() and c.kind in {"city", "town", "administrative"}:
                        out.append(
                            {
                                "city": city,
                                "country": c.country or ctry,
                                "country_code": "AE",
                                "state": c.state,
                                "kind": "city",
                                "display_name": c.display_name,
                                "osm_type": c.osm_type,
                                "osm_id": c.osm_id,
                            }
                        )
                        break
            except Exception:
                continue
    return sorted(out, key=lambda x: (x["city"], x["state"]))[:limit]


def list_districts(
    country: str,
    city: str = "",
    query: str = "",
    limit: int = 50,
    timeout: int = 30,
    lang: str = "en",
) -> list[dict[str, Any]]:
    scope = ", ".join([p for p in (city.strip(), country.strip()) if p])
    q = f"{query.strip()} {scope}".strip() if query.strip() else f"districts in {scope or country}"
    allowed = {"suburb", "quarter", "neighbourhood", "district", "city_district", "administrative", "residential"}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for search_q in [q, f"suburbs in {scope}", f"neighbourhoods in {scope}"]:
        for item in _search(search_q, limit=max(limit, 25), timeout=timeout, lang=lang):
            c = _candidate(item)
            if not c or c.kind not in allowed:
                continue
            district = c.district or c.name
            key = (district.casefold(), (c.city or city).casefold())
            if not district or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "district": district,
                    "city": c.city or city,
                    "country": c.country or country,
                    "country_code": c.country_code or (_country_code(country) or ""),
                    "state": c.state,
                    "kind": c.kind,
                    "display_name": c.display_name,
                    "osm_type": c.osm_type,
                    "osm_id": c.osm_id,
                }
            )
            if len(out) >= limit:
                return sorted(out, key=lambda x: (x["district"], x["city"]))
    return sorted(out, key=lambda x: (x["district"], x["city"]))

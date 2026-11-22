"""Flag price per sq ft far from the neighborhood median, and implausible sizes."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

Record = dict[str, Any]


def neighborhood(r: Record) -> str:
    for f in ("SubdivisionName", "PostalCode", "City"):
        if r.get(f):
            return f"{f}:{r[f]}"
    return ""


def flag_outliers(
    rows: list[Record], high: float = 2.0, low: float = 0.5, min_peers: int = 5
) -> None:
    """Compare each row with the median of the other rows in its group (leave one out)."""
    groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        price = r.get("ClosePrice") or r.get("ListPrice")
        area = r.get("LivingArea")
        r["X_PricePerSqFt"] = round(price / area, 2) if price and area else None
        if area is not None and (area < 300 or area > 15000):
            r["_flags"].append("AREA_IMPLAUSIBLE")
        if r["X_PricePerSqFt"] and neighborhood(r):
            groups[neighborhood(r)].append(i)
    for idxs in groups.values():
        if len(idxs) <= min_peers:
            continue
        for i in idxs:
            peers = [rows[j]["X_PricePerSqFt"] for j in idxs if j != i]
            ratio = rows[i]["X_PricePerSqFt"] / median(peers)
            if ratio > high:
                rows[i]["_flags"].append("PPSF_HIGH")
            elif ratio < low:
                rows[i]["_flags"].append("PPSF_LOW")

"""Group rows into properties, then into listing or sale events; build duplicates and changes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from listing_data_normalizer.address import property_key

Record = dict[str, Any]
DATE_SLACK_DAYS = 3
ATTRS = [
    "ParcelNumber",
    "SubdivisionName",
    "CountyOrParish",
    "PropertySubType",
    "BedroomsTotal",
    "BathroomsFull",
    "BathroomsHalf",
    "BathroomsTotalInteger",
    "LivingArea",
    "LivingAreaUnits",
    "LotSizeSquareFeet",
    "LotSizeAcres",
    "YearBuilt",
]
EVENT_FILL = [
    "UnparsedAddress",
    "StreetNumber",
    "StreetName",
    "City",
    "StateOrProvince",
    "PostalCode",
    "ListingId",
    "OriginalListPrice",
    "ListPrice",
    "TaxAssessedValue",
    "ListingContractDate",
    "StandardStatus",
]
CONFLICT_FIELDS = [
    "LivingArea",
    "BedroomsTotal",
    "BathroomsFull",
    "BathroomsHalf",
    "YearBuilt",
    "LotSizeAcres",
    "PropertyCondition",
    "StandardStatus",
]


class _UF:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        self.p[self.find(a)] = self.find(b)


def _close(a: date | None, b: date | None) -> bool:
    return a is None or b is None or abs((a - b).days) <= DATE_SLACK_DAYS


def kind(r: Record) -> str:
    if r.get("ClosePrice"):
        return "sale"
    return "list" if r.get("ListPrice") else "attr"


def same_event(a: Record, b: Record) -> tuple[bool, str]:
    ka, kb = kind(a), kind(b)
    if ka != kb or ka == "attr":
        return False, ""
    if ka == "sale":
        ok = a["ClosePrice"] == b["ClosePrice"] and _close(a.get("CloseDate"), b.get("CloseDate"))
        return ok, "same sale: close price matches and close dates are within 3 days"
    ok = a["ListPrice"] == b["ListPrice"] and _close(
        a.get("ListingContractDate"), b.get("ListingContractDate")
    )
    return ok, "same listing: list price matches and list dates are within 3 days"


def _event_date(r: Record) -> date:
    return r.get("CloseDate") or r.get("ListingContractDate") or date.min


def _fill(r: Record) -> int:
    return sum(1 for k, v in r.items() if not k.startswith("_") and v not in (None, ""))


def group_properties(records: list[Record]) -> list[list[int]]:
    uf = _UF(len(records))
    by_key: dict[str, int] = {}
    for i, r in enumerate(records):
        parcel = f"P:{r['ParcelNumber']}" if r.get("ParcelNumber") else ""
        for key in (property_key(r), parcel):
            if not key:
                continue
            if key in by_key:
                uf.union(i, by_key[key])
            else:
                by_key[key] = i
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(records)):
        groups[uf.find(i)].append(i)
    return list(groups.values())


def _prop_key(recs: list[Record]) -> str:
    key = next((k for k in (property_key(r) for r in recs) if k), "")
    if key:
        return key
    parcel = next((r["ParcelNumber"] for r in recs if r.get("ParcelNumber")), "")
    if parcel:
        return f"PARCEL:{parcel}"
    return f"ROW:{recs[0]['SourceFile']}:{recs[0]['SourceRow']}"


def build(
    records: list[Record], priority: dict[str, int]
) -> tuple[list[Record], list[Record], list[Record], list[list[int]]]:
    """Returns (clean rows, duplicate rows, change rows, event clusters as record indexes)."""
    clean: list[Record] = []
    dups: list[Record] = []
    changes: list[Record] = []
    clusters_out: list[list[int]] = []
    for members in group_properties(records):
        recs = [records[i] for i in members]
        ev_uf = _UF(len(recs))
        reasons: dict[tuple[int, int], str] = {}
        for x in range(len(recs)):
            for y in range(x + 1, len(recs)):
                ok, why = same_event(recs[x], recs[y])
                if ok:
                    ev_uf.union(x, y)
                    reasons[(x, y)] = why
        by_root: dict[int, list[int]] = defaultdict(list)
        for x in range(len(recs)):
            by_root[ev_uf.find(x)].append(x)
        real = [c for c in by_root.values() if kind(recs[c[0]]) != "attr"]
        attr_only = [c for c in by_root.values() if kind(recs[c[0]]) == "attr"]
        if real:
            real.sort(key=lambda c: max(_event_date(recs[i]) for i in c))
            for c in attr_only:  # absorb into the best matching event, else the latest
                real[_best_event(recs, c, real)] += c
        else:
            real = attr_only

        pkey = _prop_key(recs)
        prop_rows: list[Record] = []
        for c in real:
            idxs = sorted(
                c,
                key=lambda i: (priority.get(recs[i]["SourceFile"], 99), -_fill(recs[i]), i),
            )
            keep = recs[idxs[0]]
            out = {k: v for k, v in keep.items() if not k.startswith("_")}
            flags = list(keep.get("_flags", []))
            for j in idxs[1:]:
                other = recs[j]
                conflicts = []
                for f in CONFLICT_FIELDS:
                    a, b = out.get(f), other.get(f)
                    if a is None and b is not None:
                        out[f] = b
                    elif a is not None and b is not None and not _same(f, a, b):
                        conflicts.append(
                            f"{f}: {a} ({keep['SourceFile']}) vs {b} ({other['SourceFile']})"
                        )
                for f in ATTRS + EVENT_FILL:
                    if out.get(f) is None and other.get(f) is not None:
                        out[f] = other[f]
                if conflicts:
                    flags.append("FIELD_CONFLICT")
                dups.append(
                    {
                        "X_PropertyKey": pkey,
                        "SourceFile": other["SourceFile"],
                        "SourceRow": other["SourceRow"],
                        "KeptSourceFile": keep["SourceFile"],
                        "KeptSourceRow": keep["SourceRow"],
                        "Reason": _reason(other, reasons),
                        "Conflicts": "; ".join(conflicts),
                    }
                )
            out["X_PropertyKey"] = pkey
            out["X_Sources"] = ", ".join(dict.fromkeys(recs[i]["SourceFile"] for i in idxs))
            out["X_SourceCount"] = len(idxs)
            out["_flags"] = flags
            prop_rows.append(out)
            clusters_out.append([members[i] for i in idxs])
        for row in prop_rows:  # fill blank attributes from other events of the same property
            for f in ATTRS:
                if row.get(f) is None:
                    donor = next(
                        (o[f] for o in prop_rows if o is not row and o.get(f) is not None), None
                    )
                    if donor is not None:
                        row[f] = donor
                        row["_flags"].append(f"ATTR_FILLED:{f}")
        clean += prop_rows
        changes += _changes(pkey, prop_rows)
    return clean, dups, changes, clusters_out


def _best_event(recs: list[Record], attr: list[int], events: list[list[int]]) -> int:
    """Pick the event an attribute-only row belongs to: same listing ID and date, else latest."""
    a = recs[attr[0]]
    for n, ev in enumerate(events):
        for i in ev:
            o = recs[i]
            same_id = a.get("ListingId") and a.get("ListingId") == o.get("ListingId")
            da = a.get("ListingContractDate") or a.get("CloseDate")
            do = o.get("ListingContractDate") if kind(o) == "list" else o.get("CloseDate")
            if same_id and da is not None and do is not None and _close(da, do):
                return n
    return len(events) - 1


def _same(f: str, a: Any, b: Any) -> bool:
    if f == "LivingArea":
        return abs(float(a) - float(b)) <= 0.01 * max(float(a), float(b))
    return bool(a == b)


def _reason(other: Record, reasons: dict[tuple[int, int], str]) -> str:
    if kind(other) == "attr":
        return "attribute-only record (no price); merged into the property's latest event"
    return next(iter(reasons.values()), "same event")


def _changes(pkey: str, rows: list[Record]) -> list[Record]:
    ordered = sorted(rows, key=_event_date)
    out: list[Record] = []
    for a, b in zip(ordered, ordered[1:], strict=False):
        ka, kb = kind(a), kind(b)
        pa = a.get("ClosePrice") or a.get("ListPrice")
        pb = b.get("ClosePrice") or b.get("ListPrice")
        if kb == "sale" and ka == "list":
            ctype = "Sold after listing"
        elif ka == "list" and kb == "list":
            ida, idb = a.get("ListingId"), b.get("ListingId")
            ctype = "Relisted under a new ID" if ida and idb and ida != idb else "List price change"
        elif ka == "sale" and kb == "sale":
            ctype = "Sold again"
        elif ka == "sale" and kb == "list":
            ctype = "Listed after a sale"
        else:
            continue
        da, db = _event_date(a), _event_date(b)
        known = date.min not in (da, db)
        out.append(
            {
                "X_PropertyKey": pkey,
                "UnparsedAddress": b.get("UnparsedAddress") or a.get("UnparsedAddress"),
                "ChangeType": ctype,
                "FromDate": None if da == date.min else da,
                "FromStatus": a.get("StandardStatus"),
                "FromPrice": pa,
                "ToDate": None if db == date.min else db,
                "ToStatus": b.get("StandardStatus"),
                "ToPrice": pb,
                "PriceChange": None if pa is None or pb is None else round(pb - pa, 2),
                "PriceChangePct": None if not pa or pb is None else round(100 * (pb - pa) / pa, 1),
                "Days": (db - da).days if known else None,
            }
        )
    return out

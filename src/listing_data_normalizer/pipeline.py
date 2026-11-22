"""Row normalization: raw cells in, RESO-named record out."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from listing_data_normalizer import address as adr
from listing_data_normalizer import parsers as p
from listing_data_normalizer.headers import HeaderMatch, map_headers
from listing_data_normalizer.io import read_table

Record = dict[str, Any]


@dataclass
class Issue:
    source: str
    row: int
    field: str
    raw: str
    reason: str


@dataclass
class Result:
    records: list[Record] = field(default_factory=list)
    clean: list[Record] = field(default_factory=list)
    duplicates: list[Record] = field(default_factory=list)
    changes: list[Record] = field(default_factory=list)
    review: list[Issue] = field(default_factory=list)
    mapping: list[HeaderMatch] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    clusters: list[list[int]] = field(default_factory=list)  # record indexes per clean row


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def normalize_row(
    source: str, rownum: int, raw: dict[str, Any], matches: list[HeaderMatch], today: date
) -> tuple[Record, list[Issue]]:
    cells: dict[str, tuple[Any, str | None, str]] = {}
    for m in matches:
        if m.field and m.header in raw and not p.is_blank(raw[m.header]):
            cells[m.field] = (raw[m.header], m.unit_hint, m.header)
    rec: Record = {"SourceFile": source, "SourceRow": rownum}
    issues: list[Issue] = []
    flags: list[str] = []

    def bad(fieldname: str, value: Any, reason: str | None) -> None:
        if reason:
            issues.append(Issue(source, rownum, fieldname, _s(value), reason))

    def get(role: str) -> Any:
        return cells[role][0] if role in cells else None

    def hint(role: str) -> str | None:
        return cells[role][1] if role in cells else None

    # identifiers
    if "ListingId" in cells:
        rec["ListingId"] = _s(get("ListingId")).upper()
    if "ParcelNumber" in cells:
        pn = "".join(c for c in _s(get("ParcelNumber")).upper() if c.isalnum())
        rec["ParcelNumber"] = pn or None

    # address
    street_text, city, state, zip_raw = _s(get("Address")), "", "", ""
    if street_text:
        street_text, c2, s2, z2 = adr.split_full_address(street_text)
        city, state, zip_raw = c2, s2, z2
    city = _s(get("City")) or city
    state = _s(get("StateOrProvince")) or state
    zip_raw = _s(get("PostalCode")) or zip_raw
    if street_text:
        st, why = adr.parse_street(street_text)
        bad("Address", street_text, why)
        if st:
            rec.update(
                StreetNumber=st.number,
                StreetDirPrefix=st.prefix or None,
                StreetName=st.name,
                StreetSuffix=st.suffix or None,
                StreetDirSuffix=st.dir_suffix or None,
                UnitNumber=st.unit or None,
            )
            rec["_line"] = st.line()
    rec["City"] = adr.norm_city(city) or None
    code, why = adr.norm_state(state)
    bad("StateOrProvince", state, why)
    rec["StateOrProvince"] = code or None
    zc, why = adr.norm_zip(zip_raw)
    bad("PostalCode", zip_raw, why)
    rec["PostalCode"] = zc or None
    if rec.get("_line"):
        tail = " ".join(x for x in (rec["StateOrProvince"], rec["PostalCode"]) if x)
        rec["UnparsedAddress"] = ", ".join(x for x in (rec["_line"], rec["City"], tail) if x)
    rec.pop("_line", None)
    for role in ("CountyOrParish", "SubdivisionName"):
        if role in cells:
            rec[role] = " ".join(_s(get(role)).upper().split())

    # beds and baths
    beds = full = half = None
    if "BedBath" in cells:
        vals, msgs = p.parse_bedbath(get("BedBath"))
        beds, full, half = vals["beds"], vals["full"], vals["half"]
        for msg in msgs:
            bad("BedBath", get("BedBath"), msg)
    if "BedroomsTotal" in cells:
        v, why = p.parse_count(get("BedroomsTotal"))
        bad("BedroomsTotal", get("BedroomsTotal"), why)
        beds = v if v is not None else beds
    if "BathroomsTotal" in cells:
        tb, why = p.parse_bath_total(get("BathroomsTotal"))
        bad("BathroomsTotal", get("BathroomsTotal"), why)
        if tb:
            full, half = tb
    if "BathroomsFull" in cells:
        v, why = p.parse_count(get("BathroomsFull"))
        bad("BathroomsFull", get("BathroomsFull"), why)
        full = v if v is not None else full
        half = half if half is not None else (0 if v is not None else None)
    if "BathroomsHalf" in cells:
        v, why = p.parse_count(get("BathroomsHalf"))
        bad("BathroomsHalf", get("BathroomsHalf"), why)
        half = v if v is not None else half
        full = full if full is not None else (0 if v is not None else None)
    rec["BedroomsTotal"], rec["BathroomsFull"], rec["BathroomsHalf"] = beds, full, half
    rec["BathroomsTotalInteger"] = None if full is None else full + (half or 0)

    # size
    if "LivingArea" in cells:
        area, why = p.parse_area(get("LivingArea"), hint("LivingArea"))
        bad("LivingArea", get("LivingArea"), why)
        rec["LivingArea"] = area
        rec["LivingAreaUnits"] = "SquareFeet" if area else None
    if "LotSize" in cells:
        acres, why = p.parse_lot(get("LotSize"), hint("LotSize"))
        bad("LotSize", get("LotSize"), why)
        rec["LotSizeAcres"] = acres
        rec["LotSizeSquareFeet"] = round(acres * p.ACRE_SQFT) if acres else None

    # year, condition, type, status
    if "YearBuilt" in cells:
        yb, why = p.parse_year_built(get("YearBuilt"), today.year)
        bad("YearBuilt", get("YearBuilt"), why)
        rec["YearBuilt"] = yb
    for role, fn in (
        ("PropertyCondition", p.parse_condition),
        ("PropertySubType", p.parse_subtype),
        ("StandardStatus", p.parse_status),
    ):
        if role in cells:
            val, why = fn(get(role))
            bad(role, get(role), why)
            rec[role] = val
    rec["PropertyType"] = "Residential"

    # money and dates
    for role in ("OriginalListPrice", "ListPrice", "ClosePrice", "TaxAssessedValue"):
        if role in cells:
            price, why = p.parse_price(get(role))
            bad(role, get(role), why)
            rec[role] = price
    for role in ("ListingContractDate", "CloseDate"):
        if role in cells:
            d, why = p.parse_date(get(role), today)
            bad(role, get(role), why)
            rec[role] = d
    if rec.get("ClosePrice") and not rec.get("StandardStatus"):
        rec["StandardStatus"] = "Closed"
        flags.append("STATUS_INFERRED")
    cd, ld = rec.get("CloseDate"), rec.get("ListingContractDate")
    if cd and ld and cd < ld:
        bad("CloseDate", cd, f"close date {cd} is before list date {ld}")
    rec["_flags"] = flags
    rec["_issue_count"] = len(issues)
    return rec, issues


def normalize_files(
    paths: list[Path], overrides: dict[str, str] | None = None, today: date | None = None
) -> Result:
    today = today or date.today()
    res = Result()
    for path in paths:
        headers, rows = read_table(path)
        matches = map_headers(path.name, headers, overrides)
        res.mapping += matches
        for i, raw in enumerate(rows, start=2):
            if all(p.is_blank(v) for v in raw.values()):
                continue
            rec, issues = normalize_row(path.name, i, raw, matches, today)
            res.records.append(rec)
            res.review += issues
    return res

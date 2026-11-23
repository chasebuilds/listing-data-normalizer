"""Map source column headers to RESO Data Dictionary field names (or to a combined-input role)."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# role -> normalized header spellings. Roles are RESO field names except Address, LotSize, BedBath.
SYNONYMS: dict[str, list[str]] = {
    "ListingId": [
        "mls",
        "mls number",
        "mls no",
        "mls num",
        "mls id",
        "listing id",
        "listing number",
        "listing no",
        "list id",
        "mls",
    ],
    "ParcelNumber": [
        "parcel",
        "parcel number",
        "parcel no",
        "parcel id",
        "apn",
        "pin",
        "tax id",
        "tax parcel",
        "parcel num",
        "parcelid",
    ],
    "Address": [
        "address",
        "property address",
        "full address",
        "street address",
        "site address",
        "situs",
        "situs address",
        "location",
        "addr",
        "street",
        "prop address",
    ],
    "City": ["city", "situs city", "town", "municipality", "property city", "site city"],
    "StateOrProvince": ["state", "st", "state code", "situs state", "state or province"],
    "PostalCode": ["zip", "zip code", "postal code", "zipcode", "postal", "situs zip", "zip5"],
    "CountyOrParish": ["county", "county name", "county or parish"],
    "SubdivisionName": [
        "subdivision",
        "subdivision name",
        "neighborhood",
        "subdiv",
        "nbhd",
        "development",
    ],
    "BedBath": [
        "bed bath",
        "bed bath count",
        "br ba",
        "beds baths",
        "bd ba",
        "bedrooms bathrooms",
        "bed bath total",
        "bd ba",
    ],
    "BedroomsTotal": [
        "beds",
        "bedrooms",
        "br",
        "bd",
        "bed",
        "bedrooms total",
        "bedroom count",
        "num bedrooms",
        "bdrms",
    ],
    "BathroomsTotal": [
        "baths",
        "bathrooms",
        "ba",
        "bath",
        "bathrooms total",
        "total baths",
        "bathroom count",
        "num baths",
    ],
    "BathroomsFull": ["full baths", "full bath", "bathrooms full", "fb", "baths full"],
    "BathroomsHalf": ["half baths", "half bath", "bathrooms half", "hb", "baths half"],
    "LivingArea": [
        "living area",
        "sqft",
        "sq ft",
        "square feet",
        "square footage",
        "gla",
        "gross living area",
        "building area",
        "bldg sqft",
        "heated area",
        "living sqft",
        "finished area",
        "sf",
        "size",
        "bldg area",
        "area",
        "total sqft",
        "building size",
        "living area sqft",
    ],
    "LotSize": [
        "lot",
        "lot size",
        "lot area",
        "acreage",
        "acres",
        "land area",
        "lot sqft",
        "land size",
        "land acres",
        "lot acres",
        "site size",
    ],
    "YearBuilt": [
        "year built",
        "yr built",
        "built",
        "year blt",
        "yr blt",
        "built year",
        "year constructed",
        "construction year",
    ],
    "PropertyCondition": [
        "condition",
        "cond",
        "condition code",
        "cond cd",
        "property condition",
        "overall condition",
        "cond rating",
    ],
    "PropertySubType": [
        "property type",
        "prop type",
        "style",
        "property sub type",
        "type",
        "subtype",
        "property subtype",
        "dwelling type",
        "structure type",
    ],
    "StandardStatus": ["status", "listing status", "standard status", "mls status", "stat"],
    "ListPrice": [
        "list price",
        "listing price",
        "asking price",
        "price",
        "current price",
        "lp",
        "list",
    ],
    "OriginalListPrice": [
        "original list price",
        "orig list price",
        "original price",
        "orig price",
        "olp",
    ],
    "ClosePrice": [
        "sold price",
        "sale price",
        "close price",
        "closed price",
        "last sale price",
        "sale",
        "selling price",
        "sp",
        "sold",
        "sale amount",
        "last sale amount",
    ],
    "CloseDate": [
        "sold date",
        "sale date",
        "close date",
        "closed date",
        "closing date",
        "last sale date",
        "date sold",
        "settlement date",
        "cd",
    ],
    "ListingContractDate": [
        "list date",
        "listing date",
        "listing contract date",
        "date listed",
        "contract date",
        "on market date",
        "listed",
    ],
    "TaxAssessedValue": [
        "assessed value",
        "total assessed value",
        "tax assessed value",
        "appraised value",
        "assessment",
        "total value",
        "assessed",
        "total assessed",
    ],
}
LOOSE = {
    "price": "bare 'price' taken as list price",
    "type": "bare 'type' taken as property type",
    "area": "bare 'area' taken as living area",
    "size": "bare 'size' taken as living area",
    "sf": "'sf' taken as living area square feet",
}
_LOOKUP = {s: role for role, ss in SYNONYMS.items() for s in ss}
_UNIT_STRIP = re.compile(
    r"\b(sq ?ft|sqft|sf|ft2|sq ?m|sqm|m2|acres?|ac|ha|hectares?|sq|ft)\b", re.I
)


@dataclass
class HeaderMatch:
    source: str
    header: str
    field: str  # "" when unmapped
    method: str  # exact, override, fuzzy, duplicate, unmapped
    confidence: float
    unit_hint: str | None = None
    note: str = ""


def _squash(h: str) -> str:
    h = h.lower().replace("$", " ").replace("#", " no ").replace("²", "2")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", h)).strip()


def unit_hint(header: str) -> str | None:
    h = header.lower().replace("²", "2")
    if re.search(r"sq\.? ?m\b|sqm|\bm2\b|square met|\bsm\b", h):
        return "sqm"
    if re.search(r"acre|\bac\b", h):
        return "acre"
    if re.search(r"hectare|\bha\b", h):
        return "ha"
    if re.search(r"sq\.? ?f|sqft|\bsf\b|ft2|square f", h):
        return "sqft"
    return None


def _candidates(header: str) -> list[str]:
    base = _squash(header)
    no_paren = _squash(re.sub(r"\(.*?\)", " ", header))
    stripped = _squash(_UNIT_STRIP.sub(" ", no_paren))
    out: list[str] = []
    for c in (base, no_paren, stripped):
        if c and c not in out:
            out.append(c)
    return out


def known_header_count(cells: list[str]) -> int:
    """How many of these cells look like headers this tool knows (exact spelling after cleanup)."""
    return sum(1 for c in cells if any(x in _LOOKUP for x in _candidates(c)))


def map_headers(
    source: str, headers: list[str], overrides: dict[str, str] | None = None
) -> list[HeaderMatch]:
    overrides = {_squash(k): v for k, v in (overrides or {}).items()}
    taken: set[str] = set()
    out: list[HeaderMatch] = []
    for h in headers:
        hint = unit_hint(h)
        cands = _candidates(h)
        field, method, conf, note = "", "unmapped", 0.0, ""
        for c in cands:
            if c in overrides:
                field, method, conf = overrides[c], "override", 1.0
                break
        if not field:
            for c in cands:
                if c in _LOOKUP:
                    field, method, conf = _LOOKUP[c], "exact", 1.0
                    note = LOOSE.get(c, "")
                    if note:
                        conf = 0.75
                    break
        if not field:
            best = difflib.get_close_matches(cands[-1] if cands else "", list(_LOOKUP), 1, 0.84)
            if best:
                field, method = _LOOKUP[best[0]], "fuzzy"
                conf = round(difflib.SequenceMatcher(None, cands[-1], best[0]).ratio(), 2)
                note = f"closest spelling: {best[0]!r}"
        if field and field in taken and field != "":
            note = f"another column already maps to {field}; this one ignored"
            field, method, conf = "", "duplicate", 0.0
        elif field:
            taken.add(field)
        if not field and method == "unmapped":
            note = "no match; ignored (add it with --mapping)"
        out.append(HeaderMatch(source, h, field, method, conf, hint, note))
    return out

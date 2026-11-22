"""Street address standardization in USPS Publication 28 style (small, offline, rule based)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SUFFIXES = {
    "street": "ST",
    "st": "ST",
    "str": "ST",
    "avenue": "AVE",
    "ave": "AVE",
    "av": "AVE",
    "road": "RD",
    "rd": "RD",
    "drive": "DR",
    "dr": "DR",
    "lane": "LN",
    "ln": "LN",
    "court": "CT",
    "ct": "CT",
    "circle": "CIR",
    "cir": "CIR",
    "boulevard": "BLVD",
    "blvd": "BLVD",
    "way": "WAY",
    "trail": "TRL",
    "trl": "TRL",
    "place": "PL",
    "pl": "PL",
    "terrace": "TER",
    "ter": "TER",
    "parkway": "PKWY",
    "pkwy": "PKWY",
    "ridge": "RDG",
    "rdg": "RDG",
    "creek": "CRK",
    "crk": "CRK",
    "hollow": "HOLW",
    "holw": "HOLW",
    "hlw": "HOLW",
    "fork": "FRK",
    "frk": "FRK",
    "run": "RUN",
    "pike": "PIKE",
    "loop": "LOOP",
    "branch": "BR",
    "br": "BR",
    "hill": "HL",
    "hl": "HL",
    "alley": "ALY",
    "square": "SQ",
}
DIRECTIONS = {
    "n": "N",
    "north": "N",
    "s": "S",
    "south": "S",
    "e": "E",
    "east": "E",
    "w": "W",
    "west": "W",
    "ne": "NE",
    "northeast": "NE",
    "nw": "NW",
    "northwest": "NW",
    "se": "SE",
    "southeast": "SE",
    "sw": "SW",
    "southwest": "SW",
}
ROUTE_WORDS = {
    "hwy": "HWY",
    "highway": "HWY",
    "route": "RTE",
    "rte": "RTE",
    "rt": "RTE",
    "cr": "CR",
    "sr": "SR",
    "ky": "KY",
    "us": "US",
}
STATES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}
STATE_CODES = set(STATES.values())

_UNIT_TAIL = re.compile(
    r"[\s,]+(?:(apt|apartment|unit|ste|suite|lot|trlr|bldg|building|fl)\.?(?:\s+#?\s*|\s*#\s*)|#\s*)"
    r"([A-Za-z0-9][A-Za-z0-9\-]*)\s*$",
    re.I,
)


_UNIT_PIECE = re.compile(
    r"^(?:(?:apt|apartment|unit|ste|suite|lot|trlr|bldg|fl)\.?(?:\s+|\s*#\s*)|#\s*)[A-Za-z0-9]",
    re.I,
)


@dataclass
class Street:
    number: str = ""
    prefix: str = ""
    name: str = ""
    suffix: str = ""
    dir_suffix: str = ""
    unit: str = ""

    def line(self) -> str:
        parts = [self.number, self.prefix, self.name, self.suffix, self.dir_suffix]
        text = " ".join(p for p in parts if p)
        return f"{text} # {self.unit}" if self.unit else text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(".", " ").replace(",", " ")).strip()


def parse_street(text: str) -> tuple[Street | None, str | None]:
    raw = re.sub(r"\s+", " ", text).strip()
    if not raw:
        return None, None
    unit = ""
    m = _UNIT_TAIL.search(raw)
    if m:
        unit = m.group(2).upper()
        raw = raw[: m.start()]
    toks = _clean(raw).split(" ")
    if not toks or not re.match(r"^\d+[A-Za-z]?$", toks[0]):
        return None, f"no house number: {text!r}"
    st = Street(number=toks[0].upper(), unit=unit)
    rest = toks[1:]
    if not rest:
        return None, f"no street name: {text!r}"
    if (
        len(rest) > 1
        and rest[0].lower() in DIRECTIONS
        and not (len(rest) == 2 and rest[1].lower() in SUFFIXES)
    ):
        st.prefix = DIRECTIONS[rest[0].lower()]
        rest = rest[1:]
    if (
        len(rest) > 1
        and rest[-1].lower() in DIRECTIONS
        and (len(rest) > 2 and rest[-2].lower() in SUFFIXES)
    ):
        st.dir_suffix = DIRECTIONS[rest[-1].lower()]
        rest = rest[:-1]
    if rest and rest[0].lower() in ROUTE_WORDS and len(rest) >= 2 and rest[-1].isdigit():
        st.name = " ".join([ROUTE_WORDS[rest[0].lower()], *rest[1:]]).upper()
        return st, None
    if len(rest) > 1 and rest[-1].lower() in SUFFIXES:
        st.suffix = SUFFIXES[rest[-1].lower()]
        rest = rest[:-1]
    st.name = " ".join(rest).upper()
    return st, None


def norm_state(text: str) -> tuple[str, str | None]:
    t = re.sub(r"[.\s]+", " ", text).strip().lower()
    if not t:
        return "", None
    if t in STATES:
        return STATES[t], None
    if t.upper() in STATE_CODES:
        return t.upper(), None
    return "", f"unrecognized state: {text!r}"


def norm_zip(raw: Any) -> tuple[str, str | None]:
    t = "" if raw is None else str(raw).strip()
    if t.endswith(".0"):
        t = t[:-2]
    if not t:
        return "", None
    digits = re.sub(r"\D", "", t)
    if len(digits) == 4:
        return "0" + digits, f"ZIP had 4 digits; leading zero restored: {t!r}"
    if len(digits) == 5:
        return digits, None
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}", None
    return "", f"could not read ZIP: {t!r}"


def norm_city(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace(".", " ")).strip().upper()


def split_full_address(text: str) -> tuple[str, str, str, str]:
    """Split 'street, city, ST 41501' into pieces. Missing pieces come back empty."""
    parts: list[str] = []
    for piece in (p.strip() for p in text.split(",") if p.strip()):
        if parts and _UNIT_PIECE.match(piece):
            parts[-1] += " " + piece  # a unit after a comma belongs to the street
        else:
            parts.append(piece)
    state = zipc = city = ""
    if len(parts) >= 2:
        tail = re.match(r"^(.*?)\s*(\d{4,5}(?:-\d{4})?|\d{9})?$", parts[-1])
        if tail and tail.group(1) and norm_state(tail.group(1))[0]:
            state, zipc = tail.group(1), tail.group(2) or ""
            parts = parts[:-1]
        elif re.fullmatch(r"\d{5}(-\d{4})?", parts[-1]):
            zipc = parts[-1]
            parts = parts[:-1]
            if len(parts) >= 2 and norm_state(parts[-1])[0]:
                state = parts.pop()
        if len(parts) >= 2:
            city = parts.pop()
        return ", ".join(parts), city, state, zipc
    text = ", ".join(parts) if parts else text
    m = re.match(r"^(.*?)\s+([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$", text.strip())
    if m and m.group(2).upper() in STATE_CODES:
        return m.group(1), "", m.group(2), m.group(3)
    return text, "", "", ""


def property_key(rec: dict[str, Any]) -> str:
    """Address identity: number, direction, name, suffix, unit and 5-digit ZIP."""
    zip5 = str(rec.get("PostalCode") or "")[:5]
    unit = str(rec.get("UnitNumber") or "")
    parts = [
        rec.get("StreetNumber"),
        rec.get("StreetDirPrefix"),
        rec.get("StreetName"),
        rec.get("StreetSuffix"),
        rec.get("StreetDirSuffix"),
        unit,
        zip5,
    ]
    if not rec.get("StreetNumber") or not rec.get("StreetName"):
        return ""
    return "|".join(str(p or "") for p in parts)

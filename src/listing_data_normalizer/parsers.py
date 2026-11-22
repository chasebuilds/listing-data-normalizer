"""Value parsers. Each returns (value, issue). issue is None when the value is clean or blank."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

SQM_TO_SQFT = 10.7639104
ACRE_SQFT = 43560.0
HECTARE_ACRES = 2.47105381

PLACEHOLDERS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "-",
    "--",
    "---",
    "tbd",
    "unknown",
    "unk",
    "?",
    "nan",
    "not available",
    "not listed",
    "blank",
}


def _text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, float) and raw != raw:
        return ""
    return str(raw).strip()


def is_blank(raw: Any) -> bool:
    return _text(raw).lower() in PLACEHOLDERS


def _num(s: str) -> float | None:
    s = s.replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- price

_PRICE_RE = re.compile(
    r"^\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|m|mm|mil|million|thousand)?\.?$", re.I
)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "mil": 1e6, "million": 1e6}


def parse_price(raw: Any) -> tuple[float | None, str | None]:
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        value = float(raw)
        return (value, None) if value >= 1000 else (None, f"price under $1,000: {raw!r}")
    t = _text(raw)
    if is_blank(t):
        return None, None
    m = _PRICE_RE.match(t.replace("USD", "").strip())
    if not m:
        return None, f"could not read price: {t!r}"
    value = float(m.group(1).replace(",", "")) * _MULT.get((m.group(2) or "").lower(), 1.0)
    if value < 1000:
        return None, f"price under $1,000 (nominal transfer or typo): {t!r}"
    return round(value, 2), None


# ---------------------------------------------------------------- dates

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%m-%d-%y",
    "%m.%d.%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d-%b-%y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y%m%d",
    "%b %d, %y",
)
_DMY_FALLBACK = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")


def parse_date(raw: Any, today: date | None = None) -> tuple[date | None, str | None]:
    today = today or date.today()
    if isinstance(raw, datetime):
        d: date | None = raw.date()
        return _check_date(d, today, str(raw))
    if isinstance(raw, date):
        return _check_date(raw, today, str(raw))
    t = _text(raw)
    if is_blank(t):
        return None, None
    if re.fullmatch(r"\d{5}(\.\d+)?", t):  # Excel serial day number
        d = date(1899, 12, 30) + timedelta(days=int(float(t)))
        return _check_date(d, today, t)
    s = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", t, flags=re.I)
    s = re.sub(r"[T ]\d{1,2}:\d{2}.*$", "", s).strip().rstrip(",")
    for fmt in _DATE_FORMATS + _DMY_FALLBACK:
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        return _check_date(d, today, t)
    return None, f"could not read date: {t!r}"


def _check_date(d: date | None, today: date, shown: str) -> tuple[date | None, str | None]:
    if d is None:
        return None, None
    if d.year < 1900 or d > today + timedelta(days=366):
        return None, f"date out of range: {shown!r}"
    return d, None


# ---------------------------------------------------------------- area and lot

_UNIT_RE = re.compile(
    r"(?P<sqm>sq\.?\s*m(?:eters?|etres?)?\b|sqm\b|m2\b|m²|square\s*met\w*|sm\b)"
    r"|(?P<acre>acres?\b|ac\b|a\b)"
    r"|(?P<ha>hectares?\b|ha\b)"
    r"|(?P<sqft>sq\.?\s*f(?:ee|oo)?t\.?|sqft\b|sf\b|ft2\b|ft²|square\s*f\w*)",
    re.I,
)
_NUM_UNIT_RE = re.compile(r"^\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(.*?)\s*$")


def _unit_of(text: str) -> str | None:
    m = _UNIT_RE.search(text)
    if not m:
        return None
    return next((k for k in ("sqm", "acre", "ha", "sqft") if m.group(k)), None)


def parse_area(raw: Any, hint: str | None = None) -> tuple[float | None, str | None]:
    """Living area in square feet. hint is a unit from the column header ('sqm' or 'sqft')."""
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        value, unit, rest = float(raw), None, ""
    else:
        t = _text(raw)
        if is_blank(t):
            return None, None
        m = _NUM_UNIT_RE.match(t)
        if not m:
            return None, f"could not read area: {t!r}"
        value, rest = float(m.group(1).replace(",", "")), m.group(2)
        unit = _unit_of(rest) if rest else None
        if rest and unit is None:
            return None, f"unknown area unit: {t!r}"
    issue = None
    unit = unit or hint
    if unit == "sqm":
        value *= SQM_TO_SQFT
    elif unit is None and value < 400:
        issue = f"bare area {raw!r} taken as sq ft; could be sq m"
    if unit in ("acre", "ha"):
        return None, f"area given in land units: {raw!r}"
    if value <= 0:
        return None, f"area not positive: {raw!r}"
    return round(value, 1), issue


def parse_lot(raw: Any, hint: str | None = None) -> tuple[float | None, str | None]:
    """Lot size in acres."""
    t = "" if isinstance(raw, int | float) else _text(raw)
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        value, unit, rest = float(raw), None, ""
    else:
        if is_blank(t):
            return None, None
        dims = re.match(
            r"^\s*(\d+(?:\.\d+)?)\s*['ft]*\s*[x×]\s*(\d+(?:\.\d+)?)\s*['ft]*\s*$", t, re.I
        )
        if dims:
            return round(float(dims.group(1)) * float(dims.group(2)) / ACRE_SQFT, 4), None
        m = _NUM_UNIT_RE.match(t)
        if not m:
            return None, f"could not read lot size: {t!r}"
        value, rest = float(m.group(1).replace(",", "")), m.group(2)
        unit = _unit_of(rest) if rest else None
        if rest and unit is None:
            return None, f"unknown lot unit: {t!r}"
    issue = None
    unit = unit or hint
    if unit is None:
        unit = "acre" if value <= 200 else "sqft"
        issue = f"lot unit guessed as {'acres' if unit == 'acre' else 'sq ft'}: {raw!r}"
    if value <= 0:
        return None, f"lot size not positive: {raw!r}"
    if unit == "acre":
        acres = value
    elif unit == "ha":
        acres = value * HECTARE_ACRES
    elif unit == "sqm":
        acres = value * SQM_TO_SQFT / ACRE_SQFT
    else:
        acres = value / ACRE_SQFT
    return round(acres, 4), issue


# ---------------------------------------------------------------- beds and baths


def split_baths(value: float) -> tuple[int, int, str | None]:
    full = int(value)
    frac = round(value - full, 2)
    if frac == 0:
        return full, 0, None
    if frac == 0.5:
        return full, 1, None
    return full, 1, f"bath count {value} has a quarter fraction; counted as one half bath"


_NUM = r"(\d+(?:\.\d+)?)"
_BED_RE = re.compile(
    _NUM + r"\s*[- ]?\s*(?:br|bd|bds|bed|beds|bdrm|bdrms|bedroom|bedrooms)\b", re.I
)
_BATH_RE = re.compile(_NUM + r"\s*[- ]?\s*(?:ba|bath|baths|bathroom|bathrooms)\b", re.I)
_MIXED_BATH_RE = re.compile(r"(\d+)\s+1/2\s*[- ]?\s*(?:ba|bath|baths|bathrooms?)\b", re.I)
_FULL_RE = re.compile(r"(\d+)\s*[- ]?\s*(?:full|fb|fba)\b", re.I)
_HALF_RE = re.compile(r"(\d+)\s*[- ]?\s*(?:half|hb|hba|1/2|partial)\b", re.I)


def parse_bedbath(raw: Any) -> tuple[dict[str, int | None], list[str]]:
    """Combined text such as '3/2.5', '3 BR 2 BA', '3bd 2 full 1 half', '3/2/1' (beds/full/half)."""
    out: dict[str, int | None] = {"beds": None, "full": None, "half": None}
    issues: list[str] = []
    t = _text(raw)
    if is_blank(t):
        return out, issues
    s = t.lower()
    if "studio" in s:
        out["beds"] = 0
        s = s.replace("studio", " ")

    def take(rx: re.Pattern[str]) -> re.Match[str] | None:
        nonlocal s
        m = rx.search(s)
        if m:
            s = s[: m.start()] + " " + s[m.end() :]
        return m

    mixed = take(_MIXED_BATH_RE)
    if mixed:
        out["full"], out["half"] = int(mixed.group(1)), 1
    bed = take(_BED_RE)
    if bed:
        out["beds"] = int(float(bed.group(1)))
    if not mixed:
        full, half = take(_FULL_RE), take(_HALF_RE)
        if full:
            out["full"] = int(full.group(1))
        if half:
            out["half"] = int(half.group(1))
        bath = take(_BATH_RE)
        if bath and not full and not half:
            f, h, w = split_baths(float(bath.group(1)))
            out["full"], out["half"] = f, h
            if w:
                issues.append(w)
        elif bath and (full or half):
            issues.append(f"baths given twice in {t!r}")
        if (full or half) and out["half"] is None:
            out["half"] = 0
        if (full or half) and out["full"] is None:
            out["full"] = 0
    if out["beds"] is None and out["full"] is None:
        parts = re.fullmatch(r"\s*(\d+)\s*[/\-]\s*(\d+(?:\.\d+)?)(?:\s*[/\-]\s*(\d+))?\s*", s)
        if not parts:
            parts = re.fullmatch(r"\s*(\d+)\s*[/\-]\s*(\d+(?:\.\d+)?)(?:\s*[/\-]\s*(\d+))?\s*", t)
        if parts:
            out["beds"] = int(parts.group(1))
            if parts.group(3) is not None:
                out["full"], out["half"] = int(float(parts.group(2))), int(parts.group(3))
            else:
                f, h, w = split_baths(float(parts.group(2)))
                out["full"], out["half"] = f, h
                if w:
                    issues.append(w)
    if out["beds"] is None and out["full"] is None:
        issues.append(f"could not read bed/bath: {t!r}")
    issues += _bath_sanity(out)
    return out, issues


def _bath_sanity(vals: dict[str, int | None]) -> list[str]:
    out = []
    if vals["beds"] is not None and vals["beds"] > 20:
        out.append(f"bedroom count implausible: {vals['beds']}")
        vals["beds"] = None
    if (vals["full"] or 0) + (vals["half"] or 0) > 15:
        out.append("bath count implausible")
        vals["full"] = vals["half"] = None
    return out


def parse_count(raw: Any) -> tuple[int | None, str | None]:
    t = _text(raw)
    if is_blank(t):
        return None, None
    if t.lower() == "studio":
        return 0, None
    n = _num(t)
    if n is None or n < 0 or n != int(n):
        return None, f"could not read count: {t!r}"
    return int(n), None


def parse_bath_total(raw: Any) -> tuple[tuple[int, int] | None, str | None]:
    t = _text(raw)
    if is_blank(t):
        return None, None
    vals, issues = parse_bedbath(t if re.search(r"[a-z]", t, re.I) else t + " ba")
    if vals["full"] is None:
        return None, issues[0] if issues else f"could not read baths: {t!r}"
    return (vals["full"], vals["half"] or 0), (issues[0] if issues else None)


# ---------------------------------------------------------------- year built


def parse_year_built(raw: Any, ref_year: int | None = None) -> tuple[int | None, str | None]:
    ref_year = ref_year or date.today().year
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        raw = str(int(raw))
    t = _text(raw)
    if is_blank(t):
        return None, None
    if re.search(r"\b(new|proposed|to be built|under construction|u/c)\b", t, re.I):
        return None, f"new construction, no year stated: {t!r}"
    m = re.search(r"(?<!\d)(1[6-9]\d\d|20\d\d)(0s|s)?(?!\d)", t)
    if not m:
        return None, f"could not read year built: {t!r}"
    year = int(m.group(1))
    if year > ref_year + 2 or year < 1700:
        return None, f"year built out of range: {t!r}"
    note = f"decade only ({t!r}); first year used" if m.group(2) else None
    return year, note


# ---------------------------------------------------------------- condition, status, type

_COND_CODES = {
    "e": "Excellent",
    "ex": "Excellent",
    "exc": "Excellent",
    "g": "Good",
    "gd": "Good",
    "vg": "Good",
    "a": "Average",
    "avg": "Average",
    "av": "Average",
    "f": "Fair",
    "fr": "Fair",
    "p": "Poor",
    "pr": "Poor",
}
_COND_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Poor",
        (
            "poor",
            "fixer",
            "tear down",
            "teardown",
            "needs work",
            "needs major",
            "as-is",
            "as is",
            "distressed",
            "uninhabitable",
            "gut",
            "condemned",
            "unsound",
        ),
    ),
    (
        "Fair",
        (
            "fair to good",
            "fair/good",
            "fair-good",
            "below average",
            "fair",
            "dated",
            "needs updating",
            "needs update",
            "some repairs",
            "tlc",
            "worn",
            "deferred",
        ),
    ),
    (
        "Excellent",
        (
            "excellent",
            "like new",
            "mint",
            "newly renovated",
            "fully renovated",
            "new construction",
            "pristine",
        ),
    ),
    ("Average", ("average", "avg", "typical", "normal", "standard", "c3", "c4")),
    (
        "Good",
        (
            "good",
            "well maintained",
            "well-maintained",
            "updated",
            "move-in",
            "move in",
            "clean",
            "renovated",
            "nice",
        ),
    ),
)


def parse_condition(raw: Any) -> tuple[str | None, str | None]:
    t = _text(raw)
    if is_blank(t):
        return None, None
    low = re.sub(r"[.]", "", t.lower())
    if low in _COND_CODES:
        return _COND_CODES[low], None
    for label, words in _COND_RULES:
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in words):
            return label, None
    return None, f"unrecognized condition text: {t!r}"


_STATUS = {
    "Active": ("a", "act", "active", "new", "available", "for sale", "back on market", "bom"),
    "Active Under Contract": (
        "auc",
        "active under contract",
        "under contract",
        "uc",
        "contingent",
        "active contingent",
        "sale pending",
        "pending sale",
    ),
    "Pending": ("p", "pend", "pending", "pnd"),
    "Closed": ("s", "sold", "c", "closed", "close", "settled", "cl"),
    "Canceled": ("cancelled", "canceled", "can", "cnl", "cancel"),
    "Expired": ("x", "exp", "expired"),
    "Withdrawn": ("w", "wd", "wth", "withdrawn", "withdrawal", "off market"),
    "ComingSoon": ("coming soon", "comingsoon", "cs"),
}
_STATUS_LOOKUP = {v: k for k, vs in _STATUS.items() for v in vs}


def parse_status(raw: Any) -> tuple[str | None, str | None]:
    t = _text(raw)
    if is_blank(t):
        return None, None
    key = re.sub(r"[.\-_]", " ", t.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    if key in _STATUS_LOOKUP:
        return _STATUS_LOOKUP[key], None
    return None, f"unrecognized status: {t!r}"


def parse_subtype(raw: Any) -> tuple[str | None, str | None]:
    t = _text(raw)
    if is_blank(t):
        return None, None
    low = t.lower()
    rules = (
        ("Condominium", ("condo",)),
        ("Townhouse", ("town", "th ")),
        ("Manufactured Home", ("manufactured", "mobile", "modular", "mh")),
        ("Duplex", ("duplex", "2 unit", "two unit")),
        (
            "Single Family Residence",
            (
                "single",
                "sfr",
                "sfh",
                "detached",
                "house",
                "ranch",
                "residential",
                "cape",
                "colonial",
                "bungalow",
                "cottage",
            ),
        ),
    )
    for label, words in rules:
        if any(w in low for w in words):
            return label, None
    return None, f"unrecognized property type: {t!r}"

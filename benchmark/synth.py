"""Seeded synthetic messy exports with known truth. Every name, address and number is invented."""

from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook

TODAY = date(2026, 11, 22)
TITLED = {"county_assessor.csv"}
STREETS = [
    "Bramley",
    "Quillon",
    "Tarrow",
    "Venn",
    "Ostrander",
    "Halvard",
    "Pembrook",
    "Kestrel",
    "Dunmore",
    "Ashgrove",
    "Lindqvist",
    "Marrow",
    "Fennick",
    "Calloway",
    "Wrenfield",
    "Orlick",
    "Thistle",
    "Garrow",
    "Selwyn",
    "Brackett",
    "Hollin",
    "Yarrow",
    "Corvale",
    "Westmark",
    "Elmhurst",
    "Ravensby",
    "Tolliver",
    "Greaves",
    "Isley",
    "Norvell",
    "Ponder",
    "Quarry Hill",
    "Mill Creek",
    "Cold Spring",
    "Sugar Maple",
    "Red Fern",
]
SUFFIX_LONG = {
    "ST": ["Street", "St", "St."],
    "AVE": ["Avenue", "Ave", "Ave."],
    "RD": ["Road", "Rd", "Rd."],
    "DR": ["Drive", "Dr", "Dr."],
    "LN": ["Lane", "Ln"],
    "CT": ["Court", "Ct"],
    "CIR": ["Circle", "Cir"],
    "TRL": ["Trail", "Trl"],
    "PL": ["Place", "Pl"],
    "HOLW": ["Hollow", "Holw"],
    "FRK": ["Fork", "Frk"],
    "BR": ["Branch", "Br"],
    "RDG": ["Ridge", "Rdg"],
    "WAY": ["Way"],
}
DIR_LONG = {
    "N": "North",
    "S": "South",
    "E": "East",
    "W": "West",
    "NE": "Northeast",
    "SW": "Southwest",
}
PLACES = [  # invented towns, plausible ZIPs, base price per sq ft
    ("HARLOW CREEK", "41501", 118),
    ("MOUNT VERDEN", "41502", 96),
    ("ASHBY FORK", "41503", 82),
    ("DUNMORE GAP", "41504", 134),
    ("LENOX RIDGE", "41505", 71),
    ("TALLOW RUN", "41507", 104),
]
SUBDIVS = [
    "Cedar Rise",
    "Oakmont Terrace",
    "Willow Bend",
    "Stonegate",
    "Fox Hollow Estates",
    "Meadow Park",
    "Laurel Ridge",
    "Heritage Pointe",
]
COND_FACTOR = {"Excellent": 1.15, "Good": 1.0, "Average": 0.9, "Fair": 0.75, "Poor": 0.55}
COND_TEXT = {
    "Excellent": ["Excellent", "Like new", "Mint condition", "Newly renovated", "Pristine"],
    "Good": [
        "Good",
        "Well maintained",
        "Updated kitchen and baths",
        "Good condition",
        "Move-in ready",
    ],
    "Average": ["Average", "Avg", "Typical for age", "Average condition"],
    "Fair": ["Fair", "Dated, needs updating", "Some repairs needed", "Needs TLC", "Fair condition"],
    "Poor": ["Poor", "Fixer upper", "Needs major work", "Sold as-is, distressed", "Teardown"],
}
COND_CODE = {"Excellent": "E", "Good": "G", "Average": "A", "Fair": "F", "Poor": "P"}
SUBTYPE_TEXT = {
    "Single Family Residence": [
        "Single Family",
        "SFR",
        "Detached",
        "Ranch",
        "Single Family Residence",
    ],
    "Condominium": ["Condo", "Condominium"],
    "Townhouse": ["Townhouse", "Townhome"],
    "Manufactured Home": ["Manufactured Home", "Mobile Home"],
    "Duplex": ["Duplex"],
}
STATUS_TEXT = {
    "Active": ["Active", "A", "New", "Active"],
    "Closed": ["Sold", "Closed", "S", "Closed"],
    "Expired": ["Expired", "Exp", "X"],
}
JUNK = {
    "price": ["call agent", "ask", "$$$", "see remarks"],
    "year": ["c.19?0", "old", "see tax record"],
    "cond": ["see remarks", "ask agent", "n/a?"],
    "baths": ["ask", "several", "x/y"],
    "date": ["last week", "soon", "31/31/2024"],
}


@dataclass
class Event:
    eid: int
    kind: str  # list or sale
    listing_id: str
    when: date
    price: int
    status: str
    orig_price: int
    list_price: int
    list_date: date
    close_price: int | None = None


@dataclass
class Prop:
    pid: int
    parcel: str
    number: int
    prefix: str
    name: str
    suffix: str
    unit: str
    city: str
    zip5: str
    subdiv: str
    subtype: str
    beds: int
    full: int
    half: int
    area: int
    acres: float
    year: int
    cond: str
    outlier: bool
    ppsf: float = 0.0
    events: list[Event] = field(default_factory=list)


def _round(x: float, base: int = 500) -> int:
    return int(round(x / base) * base)


def make_props(n: int, rng: random.Random) -> list[Prop]:
    props: list[Prop] = []
    for pid in range(n):
        city, zip5, base = PLACES[rng.randrange(len(PLACES))]
        subtype = rng.choices(list(SUBTYPE_TEXT), [78, 8, 5, 6, 3])[0]
        beds = rng.choice([2, 3, 3, 3, 4, 4, 5])
        full = rng.choice([1, 2, 2, 3])
        half = rng.choice([0, 0, 1])
        area = int(rng.gauss(1300 + 260 * beds, 280) // 5 * 5)
        area = max(area, 650)
        cond = rng.choices(list(COND_FACTOR), [8, 38, 32, 15, 7])[0]
        subdiv = rng.choice(SUBDIVS) if rng.random() < 0.6 else ""
        ppsf = base * COND_FACTOR[cond] * math.exp(rng.gauss(0, 0.15))
        outlier = rng.random() < 0.03
        if outlier:
            ppsf *= rng.uniform(2.8, 5.0) if rng.random() < 0.5 else 1 / rng.uniform(2.8, 5.0)
        route = rng.random() < 0.04
        p = Prop(
            pid=pid,
            parcel=f"{rng.randrange(10, 99):02d}{rng.randrange(1, 99):02d}"
            f"{rng.randrange(1000, 9999)}{rng.randrange(0, 99):02d}",
            number=rng.randrange(1, 9999),
            prefix=rng.choice(["", "", "", "N", "S", "E", "W", "NE", "SW"]),
            name="HWY " + str(rng.randrange(15, 999)) if route else rng.choice(STREETS).upper(),
            suffix="" if route else rng.choice(list(SUFFIX_LONG)),
            unit=(
                rng.choice(["1", "2", "3", "4", "2B", "10", "7A"])
                if subtype == "Condominium"
                else ""
            ),
            city=city,
            zip5=zip5,
            subdiv=subdiv.upper(),
            subtype=subtype,
            beds=beds,
            full=full,
            half=half,
            area=area,
            acres=round(
                rng.choice([0.12, 0.2, 0.25, 0.3, 0.5, 1.0, 2.5, 5.0, 12.4, rng.uniform(0.1, 30)]),
                2,
            ),
            year=rng.randrange(1925, 2025),
            cond=cond,
            outlier=outlier,
        )
        if route:
            p.prefix = ""
        p.ppsf = ppsf
        base_price = ppsf * area
        eid = 0
        d0 = date(2023, 1, 1) + timedelta(days=rng.randrange(0, 1000))
        if rng.random() < 0.25:  # earlier listing that expired
            p.events.append(
                Event(
                    eid,
                    "list",
                    f"{rng.randrange(10**6, 10**7)}",
                    d0,
                    _round(base_price * 1.15),
                    "Expired",
                    _round(base_price * 1.15),
                    _round(base_price * 1.15),
                    d0,
                )
            )
            eid += 1
            d0 += timedelta(days=rng.randrange(60, 200))
        lid = f"{rng.randrange(10**6, 10**7)}"
        p1 = _round(base_price * 1.07)
        sale = rng.random() < 0.7
        p.events.append(Event(eid, "list", lid, d0, p1, "Active", p1, p1, d0))
        eid += 1
        last_list, last_date = p1, d0
        if rng.random() < 0.35:
            last_date = d0 + timedelta(days=rng.randrange(20, 70))
            last_list = _round(base_price * 1.02)
            p.events.append(
                Event(eid, "list", lid, last_date, last_list, "Active", p1, last_list, d0)
            )
            eid += 1
        if sale:
            cd = last_date + timedelta(days=rng.randrange(20, 90))
            cp = _round(base_price * rng.uniform(0.96, 1.0), 100)
            p.events.append(Event(eid, "sale", lid, cd, cp, "Closed", p1, last_list, d0, cp))
        props.append(p)
    # keep every date in the past
    for p in props:
        p.events = [e for e in p.events if e.when <= TODAY - timedelta(days=5)]
        for i, e in enumerate(p.events):
            e.eid = i
    return [p for p in props if p.events]


# ------------------------------------------------------------------ formatting helpers


def street_text(p: Prop, rng: random.Random) -> str:
    parts = [str(p.number)]
    if p.prefix:
        parts.append(
            DIR_LONG[p.prefix] if rng.random() < 0.3 and p.prefix in DIR_LONG else p.prefix
        )
    name = p.name.title()
    if p.name.startswith("HWY"):
        name = rng.choice(["Hwy", "Highway"]) + p.name[3:]
    parts.append(name)
    if p.suffix:
        parts.append(rng.choice(SUFFIX_LONG[p.suffix]))
    text = " ".join(parts)
    if p.unit:
        form = rng.choice(["Apt {}", "#{}", "Unit {}", "Apt. {}", "# {}"]).format(p.unit)
        text += rng.choice([" ", ", "]) + form
    return rng.choice([text, text, text.upper(), text.lower()])


def expected_line(p: Prop) -> str:
    parts = [str(p.number), p.prefix, p.name, p.suffix]
    s = " ".join(x for x in parts if x)
    return f"{s} # {p.unit}" if p.unit else s


def expected_addr(p: Prop, zipv: str) -> str:
    return f"{expected_line(p)}, {p.city}, KY {zipv}"


def fmt_date(d: date, rng: random.Random) -> str:
    f = rng.choice(
        [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%b %d, %Y",
            "%d-%b-%y",
            "%Y%m%d",
            "%B %d, %Y",
            "%m/%d/%Y",
        ]
    )
    return d.strftime(f)


def fmt_price(v: int, rng: random.Random) -> str:
    opts = [f"${v:,}", f"{v}", f"{v:,}.00", f"${v:,}"]
    if v % 100 == 0:
        opts.append(f"${v / 1000:g}K")
        opts.append(f"{v / 1000:g}k")
    return rng.choice(opts)


def fmt_baths(full: int, half: int, rng: random.Random) -> str:
    if half == 0:
        return rng.choice([str(full), f"{full}.0", f"{full} ba", f"{full} baths"])
    return rng.choice([f"{full + 0.5:g}", f"{full} full, 1 half", f"{full} 1/2 baths"])


def fmt_bedbath(beds: int, full: int, half: int, rng: random.Random) -> str:
    bath = f"{full + 0.5 * half:g}"
    opts = [
        f"{beds}/{bath}",
        f"{beds} BR {bath} BA",
        f"{beds}bd/{bath}ba",
        f"{beds} bed {bath} bath",
    ]
    if half:
        opts += [f"{beds}/{full}/{half}", f"{beds} BR {full} full {half} half"]
    return rng.choice(opts)


def fmt_lot(acres: float, rng: random.Random, mode: str) -> str:
    sqft = round(acres * 43560)
    if mode == "acres":
        return f"{acres:g}"
    return rng.choice(
        [
            f"{acres:g} ac",
            f"{sqft:,} sqft",
            f"{acres:g} acres",
            f"{sqft} sf",
            f"{acres:g}" if acres <= 200 else f"{acres:g} ac",
        ]
    )


# ------------------------------------------------------------------ source writers

Row = tuple[dict[str, Any], dict[str, Any], int, int, list[str]]  # raw, expected, pid, eid, junk


def build(n: int, seed: int, outdir: Path) -> dict[str, Any]:
    rng = random.Random(seed)
    props = make_props(n, rng)
    outdir.mkdir(parents=True, exist_ok=True)
    files: dict[str, list[Row]] = {
        "mls_a.csv": [],
        "mls_b.csv": [],
        "county_assessor.csv": [],
        "comps_list.xlsx": [],
    }

    def blank(prob: float = 0.04) -> bool:
        return rng.random() < prob

    def junk(kind: str, junks: list[str], name: str, prob: float = 0.02) -> str | None:
        if rng.random() < prob:
            junks.append(name)
            return rng.choice(JUNK[kind])
        return None

    for p in props:
        zip_variants = [p.zip5, p.zip5, p.zip5, f"{p.zip5}-{rng.randrange(1000, 9999)}"]
        for e in p.events:
            # ---- MLS style A
            if rng.random() < 0.85:
                junks: list[str] = []
                zv = rng.choice(zip_variants)
                raw: dict[str, Any] = {}
                exp: dict[str, Any] = {}
                raw["MLS #"] = e.listing_id
                exp["ListingId"] = e.listing_id
                raw["Status"] = rng.choice(STATUS_TEXT[e.status])
                exp["StandardStatus"] = e.status
                lp = junk("price", junks, "ListPrice")
                raw["List Price"] = lp or fmt_price(e.list_price, rng)
                exp["ListPrice"] = None if lp else e.list_price
                raw["List Date"] = fmt_date(e.when if e.kind == "list" else e.list_date, rng)
                exp["ListingContractDate"] = e.when if e.kind == "list" else e.list_date
                raw["Sold Price"] = fmt_price(e.close_price, rng) if e.close_price else ""
                exp["ClosePrice"] = e.close_price
                raw["Sold Date"] = fmt_date(e.when, rng) if e.kind == "sale" else ""
                exp["CloseDate"] = e.when if e.kind == "sale" else None
                raw["Address"] = street_text(p, rng)
                exp["UnparsedAddress"] = expected_addr(p, zv)
                raw["City"] = rng.choice([p.city.title(), p.city, p.city.lower()])
                raw["St"] = rng.choice(["KY", "KY", "Ky", "Kentucky"])
                raw["Zip"] = zv
                exp["PostalCode"] = zv
                raw["Subdivision"] = p.subdiv.title() if not blank(0.4) else ""
                raw["Beds"] = "" if blank() else p.beds
                exp["BedroomsTotal"] = None if raw["Beds"] == "" else p.beds
                jb = junk("baths", junks, "BathroomsFull")
                raw["Baths"] = jb or fmt_baths(p.full, p.half, rng)
                if jb:
                    exp["BathroomsFull"] = exp["BathroomsHalf"] = None
                else:
                    exp["BathroomsFull"], exp["BathroomsHalf"] = p.full, p.half
                raw["SqFt"] = "" if blank() else f"{p.area:,}" if rng.random() < 0.5 else p.area
                exp["LivingArea"] = None if raw["SqFt"] == "" else float(p.area)
                raw["Lot Size"] = fmt_lot(p.acres, rng, "mixed")
                exp["LotSizeAcres"] = p.acres
                jy = junk("year", junks, "YearBuilt")
                raw["Yr Built"] = jy or p.year
                exp["YearBuilt"] = None if jy else p.year
                jc = junk("cond", junks, "PropertyCondition", 0.05)
                raw["Condition"] = jc or rng.choice(COND_TEXT[p.cond])
                exp["PropertyCondition"] = None if jc else p.cond
                raw["Style"] = rng.choice(SUBTYPE_TEXT[p.subtype])
                exp["PropertySubType"] = p.subtype
                files["mls_a.csv"].append((raw, exp, p.pid, e.eid, junks))
                if rng.random() < 0.08:  # exact re-export of the same event
                    files["mls_a.csv"].append((dict(raw), dict(exp), p.pid, e.eid, list(junks)))
            # ---- MLS style B (metric living area, different headers)
            if rng.random() < 0.3:
                junks = []
                zv = rng.choice(zip_variants)
                raw = {}
                exp = {}
                raw["Listing ID"] = e.listing_id
                exp["ListingId"] = e.listing_id
                raw["Listing Status"] = rng.choice(STATUS_TEXT[e.status])
                exp["StandardStatus"] = e.status
                raw["Asking Price"] = fmt_price(e.list_price, rng)
                exp["ListPrice"] = e.list_price
                raw["Date Listed"] = fmt_date(e.when if e.kind == "list" else e.list_date, rng)
                exp["ListingContractDate"] = e.when if e.kind == "list" else e.list_date
                raw["Selling Price"] = fmt_price(e.close_price, rng) if e.close_price else ""
                exp["ClosePrice"] = e.close_price
                raw["Closing Date"] = fmt_date(e.when, rng) if e.kind == "sale" else ""
                exp["CloseDate"] = e.when if e.kind == "sale" else None
                raw["Property Address"] = f"{street_text(p, rng)}, {p.city.title()}, KY {zv}"
                exp["UnparsedAddress"] = expected_addr(p, zv)
                exp["PostalCode"] = zv
                raw["Bedrooms"] = p.beds
                exp["BedroomsTotal"] = p.beds
                raw["Bathrooms"] = f"{p.full + 0.5 * p.half:g}"
                exp["BathroomsFull"], exp["BathroomsHalf"] = p.full, p.half
                raw["GLA (m2)"] = f"{p.area / 10.7639104:.2f}"
                exp["LivingArea"] = float(p.area)
                raw["Acreage"] = f"{p.acres:g}"
                exp["LotSizeAcres"] = p.acres
                raw["Year Built"] = p.year
                exp["YearBuilt"] = p.year
                raw["Overall Condition"] = rng.choice(COND_TEXT[p.cond])
                exp["PropertyCondition"] = p.cond
                raw["Parcel"] = p.parcel if rng.random() < 0.4 else ""
                files["mls_b.csv"].append((raw, exp, p.pid, e.eid, junks))
        # ---- county assessor: one row per property, last sale only
        sales = [e for e in p.events if e.kind == "sale"]
        junks = []
        zv = rng.choice(zip_variants)
        raw = {}
        exp = {}
        raw["PARCEL_ID"] = rng.choice([p.parcel, f"{p.parcel[:2]}-{p.parcel[2:4]}-{p.parcel[4:]}"])
        exp["ParcelNumber"] = p.parcel
        no_unit = bool(p.unit) and rng.random() < 0.5
        ap = Prop(**{**p.__dict__, "unit": "" if no_unit else p.unit})
        raw["SITUS"] = street_text(ap, rng).upper()
        exp["UnparsedAddress"] = expected_addr(ap, zv)
        raw["SITUS_CITY"] = p.city
        raw["STATE"] = "KY"
        raw["ZIP"] = zv
        exp["PostalCode"] = zv
        raw["LAND_ACRES"] = f"{p.acres:g}"
        exp["LotSizeAcres"] = p.acres
        area = p.area if rng.random() < 0.7 else int(p.area * rng.uniform(0.95, 1.05))
        raw["BLDG_SQFT"] = area
        exp["LivingArea"] = float(area)
        raw["YR_BLT"] = p.year
        exp["YearBuilt"] = p.year
        raw["BEDS"], exp["BedroomsTotal"] = p.beds, p.beds
        raw["FULL_BATH"], raw["HALF_BATH"] = p.full, p.half
        exp["BathroomsFull"], exp["BathroomsHalf"] = p.full, p.half
        raw["COND_CD"] = COND_CODE[p.cond] if rng.random() > 0.15 else ""
        exp["PropertyCondition"] = p.cond if raw["COND_CD"] else None
        raw["SUBDIVISION"] = p.subdiv
        if sales:
            s = sales[-1]
            jd = s.when + timedelta(days=rng.randrange(0, 3))
            raw["LAST_SALE_PRICE"] = fmt_price(s.close_price or 0, rng)
            raw["LAST_SALE_DATE"] = fmt_date(jd, rng)
            exp["ClosePrice"], exp["CloseDate"] = s.close_price, jd
            exp["StandardStatus"] = "Closed"
            sale_eid = s.eid
        else:
            raw["LAST_SALE_PRICE"], raw["LAST_SALE_DATE"] = "", ""
            sale_eid = -1
        raw["ASSESSED_VALUE"] = fmt_price(_round(p.events[-1].price * 0.8), rng)
        files["county_assessor.csv"].append((raw, exp, p.pid, sale_eid, junks))
        # ---- spreadsheet comps: sales only
        if sales and rng.random() < 0.4:
            s = sales[-1]
            junks = []
            zv = p.zip5
            raw = {}
            exp = {}
            raw["Addr"] = f"{street_text(p, rng)}, {p.city.title()}, KY {zv}"
            exp["UnparsedAddress"] = expected_addr(p, zv)
            exp["PostalCode"] = zv
            raw["Bed/Bath"] = fmt_bedbath(p.beds, p.full, p.half, rng)
            exp["BedroomsTotal"], exp["BathroomsFull"], exp["BathroomsHalf"] = (
                p.beds,
                p.full,
                p.half,
            )
            raw["Sq Ft"] = p.area
            exp["LivingArea"] = float(p.area)
            raw["Lot"] = fmt_lot(p.acres, rng, "mixed")
            exp["LotSizeAcres"] = p.acres
            raw["Yr Built"] = p.year
            exp["YearBuilt"] = p.year
            raw["Cond"] = rng.choice(COND_TEXT[p.cond])
            exp["PropertyCondition"] = p.cond
            raw["Sale $"] = (
                s.close_price if rng.random() < 0.5 else fmt_price(s.close_price or 0, rng)
            )
            exp["ClosePrice"] = s.close_price
            mode = rng.random()
            raw["Sale Date"] = (
                datetime(s.when.year, s.when.month, s.when.day)
                if mode < 0.4
                else (s.when - date(1899, 12, 30)).days
                if mode < 0.5
                else fmt_date(s.when, rng)
            )
            exp["CloseDate"] = s.when
            exp["StandardStatus"] = "Closed"
            files["comps_list.xlsx"].append((raw, exp, p.pid, s.eid, junks))

    truth: dict[str, Any] = {}
    for name, rows in files.items():
        rng.shuffle(rows)
        headers = list(dict.fromkeys(k for r in rows for k in r[0]))
        if name.endswith(".csv"):
            with (outdir / name).open("w", newline="", encoding="utf-8") as fh:
                if name in TITLED:  # a county report: title lines above the table, footer below
                    fh.write("Invented County Property Report\n")
                    fh.write("Run date 11/20/2026\n\n")
                w = csv.DictWriter(fh, headers)
                w.writeheader()
                w.writerows(r[0] for r in rows)
                if name in TITLED:
                    fh.write(f"Total records: {len(rows)}\n")
        else:
            wb = Workbook()
            ws = wb.active
            ws.append(headers)
            for r in rows:
                ws.append([r[0].get(h) for h in headers])
            wb.save(outdir / name)
        for i, (_raw, exp, pid, eid, junks) in enumerate(rows, start=5 if name in TITLED else 2):
            truth[f"{name}|{i}"] = {
                "pid": pid,
                "eid": eid,
                "junk": junks,
                "expected": {
                    k: (v.isoformat() if isinstance(v, date) else v) for k, v in exp.items()
                },
            }
    by_pid = {p.pid: p for p in props}
    meta = {
        "props": len(props),
        "outlier_pids": [p.pid for p in props if p.outlier],
        "ppsf_known": {str(pid): p.outlier for pid, p in by_pid.items()},
        "ppsf": {str(pid): p.ppsf for pid, p in by_pid.items()},
        "zip": {str(pid): p.zip5 for pid, p in by_pid.items()},
    }
    (outdir / "truth.json").write_text(json.dumps({"rows": truth, "meta": meta}), encoding="utf-8")
    return {"rows": truth, "meta": meta}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="write synthetic messy exports and truth.json")
    ap.add_argument("--properties", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("samples"))
    a = ap.parse_args()
    info = build(a.properties, a.seed, a.out)
    print(f"{info['meta']['props']} houses, {len(info['rows'])} rows written to {a.out}")

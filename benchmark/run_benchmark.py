"""Run the tool on seeded synthetic exports and write BENCHMARK.md (and the README table)."""

from __future__ import annotations

import argparse
import platform
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

from benchmark.synth import TODAY, build
from listing_data_normalizer.core import normalize

ROOT = Path(__file__).resolve().parent.parent
FILES = ["mls_a.csv", "mls_b.csv", "county_assessor.csv", "comps_list.xlsx"]
HEADER_TRUTH = {
    "MLS #": "ListingId",
    "Status": "StandardStatus",
    "List Price": "ListPrice",
    "List Date": "ListingContractDate",
    "Sold Price": "ClosePrice",
    "Sold Date": "CloseDate",
    "Address": "Address",
    "City": "City",
    "St": "StateOrProvince",
    "Zip": "PostalCode",
    "Subdivision": "SubdivisionName",
    "Beds": "BedroomsTotal",
    "Baths": "BathroomsTotal",
    "SqFt": "LivingArea",
    "Lot Size": "LotSize",
    "Yr Built": "YearBuilt",
    "Condition": "PropertyCondition",
    "Style": "PropertySubType",
    "Listing ID": "ListingId",
    "Listing Status": "StandardStatus",
    "Asking Price": "ListPrice",
    "Date Listed": "ListingContractDate",
    "Selling Price": "ClosePrice",
    "Closing Date": "CloseDate",
    "Property Address": "Address",
    "Bedrooms": "BedroomsTotal",
    "Bathrooms": "BathroomsTotal",
    "GLA (m2)": "LivingArea",
    "Acreage": "LotSize",
    "Year Built": "YearBuilt",
    "Overall Condition": "PropertyCondition",
    "Parcel": "ParcelNumber",
    "PARCEL_ID": "ParcelNumber",
    "SITUS": "Address",
    "SITUS_CITY": "City",
    "STATE": "StateOrProvince",
    "ZIP": "PostalCode",
    "LAND_ACRES": "LotSize",
    "BLDG_SQFT": "LivingArea",
    "YR_BLT": "YearBuilt",
    "BEDS": "BedroomsTotal",
    "FULL_BATH": "BathroomsFull",
    "HALF_BATH": "BathroomsHalf",
    "COND_CD": "PropertyCondition",
    "SUBDIVISION": "SubdivisionName",
    "LAST_SALE_PRICE": "ClosePrice",
    "LAST_SALE_DATE": "CloseDate",
    "ASSESSED_VALUE": "TaxAssessedValue",
    "Addr": "Address",
    "Bed/Bath": "BedBath",
    "Sq Ft": "LivingArea",
    "Lot": "LotSize",
    "Cond": "PropertyCondition",
    "Sale $": "ClosePrice",
    "Sale Date": "CloseDate",
}
SCORED = [
    "UnparsedAddress",
    "PostalCode",
    "BedroomsTotal",
    "BathroomsFull",
    "BathroomsHalf",
    "LivingArea",
    "LotSizeAcres",
    "YearBuilt",
    "PropertyCondition",
    "ListPrice",
    "ClosePrice",
    "ListingContractDate",
    "CloseDate",
    "StandardStatus",
    "ListingId",
    "ParcelNumber",
]


def _eq(f: str, got: Any, want: Any) -> bool:
    if got is None or want is None:
        return got is None and want is None
    if f == "LivingArea":
        return abs(float(got) - float(want)) <= 1.0
    if f == "LotSizeAcres":
        return abs(float(got) - float(want)) <= 0.006
    if isinstance(got, date):
        return bool(got.isoformat() == want)
    return bool(got == want)


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def run(n: int, seed: int) -> str:
    data = ROOT / "benchmark" / "data"
    truth = build(n, seed, data)
    rows, meta = truth["rows"], truth["meta"]
    paths = [data / f for f in FILES]
    t0 = time.perf_counter()
    res = normalize(paths, today=TODAY)
    secs = time.perf_counter() - t0

    # header mapping
    maps = [m for m in res.mapping]
    right = sum(1 for m in maps if m.field == HEADER_TRUTH.get(m.header, "?"))
    # field accuracy
    stats: dict[str, Counter[str]] = {f: Counter() for f in SCORED}
    wrong_examples: dict[str, list[str]] = defaultdict(list)
    all_right_rows = 0
    issues_by_row = Counter((i.source, i.row) for i in res.review)
    junk_total = junk_blank = junk_flagged = 0
    for rec in res.records:
        key = f"{rec['SourceFile']}|{rec['SourceRow']}"
        exp = rows[key]["expected"]
        row_ok = True
        for f, want in exp.items():
            if f not in stats:
                continue
            got = rec.get(f)
            ok = _eq(f, got, want)
            row_ok &= ok
            if want is not None:
                stats[f]["n"] += 1
                stats[f]["ok"] += ok
                if not ok and len(wrong_examples[f]) < 3:
                    wrong_examples[f].append(f"{key}: got {got!r}, expected {want!r}")
            elif got is not None:
                stats[f]["false_value"] += 1
        for f in rows[key]["junk"]:
            junk_total += 1
            junk_blank += rec.get(f) is None
            junk_flagged += issues_by_row[(rec["SourceFile"], rec["SourceRow"])] > 0
        all_right_rows += row_ok
    cells = sum(s["n"] for s in stats.values())
    cells_ok = sum(s["ok"] for s in stats.values())

    # duplicates and events (pairs of rows from the same true listing or sale event)
    rec_truth = [rows[f"{r['SourceFile']}|{r['SourceRow']}"] for r in res.records]
    by_event: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, t in enumerate(rec_truth):
        if t["eid"] >= 0:
            by_event[(t["pid"], t["eid"])].append(i)
    true_pairs = sum(len(v) * (len(v) - 1) // 2 for v in by_event.values())
    pred_pairs = tp = 0
    for cl in res.clusters:
        scored = [i for i in cl if rec_truth[i]["eid"] >= 0]
        for a, b in combinations(scored, 2):
            pred_pairs += 1
            tp += (rec_truth[a]["pid"], rec_truth[a]["eid"]) == (
                rec_truth[b]["pid"],
                rec_truth[b]["eid"],
            )
    scored_events = [cl for cl in res.clusters if any(rec_truth[i]["eid"] >= 0 for i in cl)]
    exact = sum(
        1
        for cl in scored_events
        if {(rec_truth[i]["pid"], rec_truth[i]["eid"]) for i in cl if rec_truth[i]["eid"] >= 0}
        and len(
            {(rec_truth[i]["pid"], rec_truth[i]["eid"]) for i in cl if rec_truth[i]["eid"] >= 0}
        )
        == 1
        and len(cl)
        == len(
            by_event[
                next(
                    (rec_truth[i]["pid"], rec_truth[i]["eid"])
                    for i in cl
                    if rec_truth[i]["eid"] >= 0
                )
            ]
        )
    )

    # outliers: true when the house's real price per sq ft is more than 2x, or less than half,
    # the median of all houses in its ZIP
    by_zip: dict[str, list[float]] = defaultdict(list)
    for pid, v in meta["ppsf"].items():
        by_zip[meta["zip"][pid]].append(v)
    zmed = {z: statistics.median(v) for z, v in by_zip.items()}

    def truly_off(pid: str) -> bool:
        r = meta["ppsf"][pid] / zmed[meta["zip"][pid]]
        return bool(r > 2.0 or r < 0.5)

    flagged = truth_out = hit = inj_total = inj_hit = 0
    for row, cl in zip(res.clean, res.clusters, strict=True):
        pid = str(rec_truth[cl[0]]["pid"])
        is_out, is_flag = truly_off(pid), "PPSF" in row["X_Flags"]
        flagged += is_flag
        truth_out += is_out
        hit += is_flag and is_out
        if meta["ppsf_known"][pid]:
            inj_total += 1
            inj_hit += is_flag

    lines = [
        "# Benchmark",
        "",
        f"Written by `benchmark/run_benchmark.py` on {date.today().isoformat()} from a real run.",
        "No number on this page was typed by hand.",
        "",
        f"Command: `python -m benchmark.run_benchmark --seed {seed} --properties {n}`",
        f"Python {platform.python_version()} on {platform.system()}.",
        f"Normalizing all {len(res.records):,} rows from 4 files took {secs:.2f} s.",
        "",
        "## Method",
        "",
        f"1. Invent {meta['props']:,} fake houses: made-up streets and towns, real state code, "
        "price per sq ft that depends on town and condition, 1 to 4 events each (an expired "
        "listing, a listing, a price cut, a sale). About 3% are priced 2.8x to 5x above or "
        "below their town on purpose.",
        "2. Write them out the way four systems would: two MLS-style exports with different "
        "headers (one in square meters, one repeating some rows), a county assessor file "
        "(last sale only, some units dropped, areas that disagree by up to 5%), and a spreadsheet "
        "comps list in Excel (sales only, `3/2.5` style bed/bath, dates as real dates, text and "
        "serial numbers).",
        "3. Mess up every field: price as `$249,900`, `249.9K` or `249,900.00`; seven date "
        "formats; lot as acres, sq ft or bare; baths as `2.5`, `2 full, 1 half` or `2 1/2 baths`; "
        "free-text condition; suffixes spelled or abbreviated; units as `Apt 4`, `#4`, `Unit 4`. "
        "About 2% of some fields get junk (`call agent`, `see remarks`) that should be left blank "
        "and flagged.",
        "4. Score each normalized row, before duplicates are merged, against the answer for that "
        "row. A field counts only when the row's source had a usable value. The score is exact, "
        "except living area (within 1 sq ft) and lot acres (within 0.006).",
        "5. Duplicates: every pair of rows describing the same listing or sale of the same "
        "house is a true pair. A pair is found when both rows end in the same merged row.",
        "6. Outliers: a merged row is truly off-market when its house's real price per sq ft is "
        "more than 2x or less than half the median of its ZIP (this includes about 3% priced "
        "that way on purpose and some poor-condition houses). It is found when it carries a "
        "PPSF_HIGH or PPSF_LOW flag.",
        "",
        "## Result",
        "",
        "<!-- benchmark:start -->",
        "| Measure | Result |",
        "|---|---:|",
        f"| Rows in (4 files, {meta['props']:,} fake houses) | {len(res.records):,} |",
        f"| Headers mapped to the right RESO field | **{pct(right, len(maps))}** ({right} of {len(maps)}) |",
        f"| Fields right, exact (rows where the source had a value) | **{pct(cells_ok, cells)}** ({cells_ok:,} of {cells:,}) |",
        f"| Rows with every scored field right | {pct(all_right_rows, len(res.records))} |",
        f"| Junk values left blank | {pct(junk_blank, junk_total)} ({junk_blank} of {junk_total}) |",
        f"| Junk rows flagged in Review | {pct(junk_flagged, junk_total)} |",
        f"| Duplicate pairs found (recall) | **{pct(tp, true_pairs)}** ({tp:,} of {true_pairs:,}) |",
        f"| Duplicate pairs that were right (precision) | **{pct(tp, pred_pairs)}** ({tp:,} of {pred_pairs:,}) |",
        f"| Merged rows that match one true event exactly | {pct(exact, len(scored_events))} |",
        f"| Off-market rows found (recall) | **{pct(hit, truth_out)}** ({hit} of {truth_out}) |",
        f"| Of those, rows priced off-market on purpose that were found | {pct(inj_hit, inj_total)} ({inj_hit} of {inj_total}) |",
        f"| Outlier flags that were right (precision) | **{pct(hit, flagged)}** ({hit} of {flagged}) |",
        "<!-- benchmark:end -->",
        "",
        "## Field accuracy",
        "",
        "| Field | Right | Of | Wrong or left blank | Value where none was due |",
        "|---|---:|---:|---:|---:|",
    ]
    for f in SCORED:
        s = stats[f]
        lines.append(
            f"| {f} | {pct(s['ok'], s['n'])} | {s['n']:,} | "
            f"{s['n'] - s['ok']:,} | {s['false_value']} |"
        )
    lines += ["", "## Examples of misses", ""]
    for f, ex in wrong_examples.items():
        lines += [f"- **{f}**: " + "; ".join(f"`{e}`" for e in ex)]
    if not wrong_examples:
        lines.append("None in this run.")
    lines += [
        "",
        "## What the misses are",
        "",
        "Read the examples above (if any) against [LIMITATIONS.md](LIMITATIONS.md). The data "
        "is invented by the same author who wrote the parsers, so field accuracy here is a "
        "regression guard, not a promise: a real export will have formats this generator never "
        "thought of, and those go to the Review sheet.",
        "",
        "Duplicate misses come mostly from a source that dropped the unit number and had no "
        "parcel to link the rows, and from listings whose price was junk. Outlier misses and "
        "false flags come from list and sale prices that differ from the real price per sq ft, "
        "and from comparing by subdivision when one source gives it and another does not.",
        "",
    ]
    out = "\n".join(lines)
    (ROOT / "BENCHMARK.md").write_text(out, encoding="utf-8")
    table = re.search(r"<!-- benchmark:start -->.*?<!-- benchmark:end -->", out, re.S)
    readme = ROOT / "README.md"
    if table and readme.exists():
        text = readme.read_text(encoding="utf-8")
        if "<!-- benchmark:start -->" in text:
            text = re.sub(
                r"<!-- benchmark:start -->.*?<!-- benchmark:end -->",
                lambda _: table.group(0),
                text,
                flags=re.S,
            )
            readme.write_text(text, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261122)
    ap.add_argument("--properties", type=int, default=3000)
    args = ap.parse_args()
    print(run(args.properties, args.seed))


if __name__ == "__main__":
    main()

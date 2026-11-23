"""Command line: listnorm map FILE ... | listnorm clean FILE ... -o OUTDIR"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from listing_data_normalizer import __version__
from listing_data_normalizer.core import (
    DISCLAIMER,
    load_overrides,
    mapping_template,
    normalize,
    select_comps,
    write_outputs,
)
from listing_data_normalizer.io import write_csv

MAP_COLUMNS = ["source_header", "field", "source_file", "method", "confidence", "unit_hint", "note"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="listnorm", description=DISCLAIMER)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("map", help="dry run: write the header mapping as an editable CSV")
    m.add_argument("files", nargs="+", type=Path)
    m.add_argument("-o", "--out", type=Path, default=Path("mapping.csv"))
    m.add_argument("--mapping", type=Path, help="start from an existing mapping CSV")

    c = sub.add_parser("clean", help="normalize one or more CSV/XLSX exports")
    c.add_argument("files", nargs="+", type=Path, help="first file wins when sources disagree")
    c.add_argument("-o", "--out", type=Path, default=Path("ldn-out"))
    c.add_argument("--mapping", type=Path, help="CSV with columns source_header,field")
    c.add_argument("--no-parquet", action="store_true")
    c.add_argument("--outlier-high", type=float, default=2.0)
    c.add_argument("--outlier-low", type=float, default=0.5)
    g = c.add_argument_group("comps shortlist (closed sales only, a data filter, not a value)")
    g.add_argument("--comps", action="store_true", help="also write comps.csv and a Comps sheet")
    g.add_argument("--closed-since", type=date.fromisoformat, metavar="YYYY-MM-DD")
    g.add_argument("--zip", action="append", default=[], help="keep this ZIP (repeatable)")
    g.add_argument("--keep-flagged", action="store_true", help="do not drop outlier-flagged rows")
    args = ap.parse_args(argv)

    if args.cmd == "map":
        rows = mapping_template(args.files, load_overrides(args.mapping))
        write_csv(args.out, MAP_COLUMNS, rows)
        blank = sum(1 for r in rows if not r["field"])
        print(f"{len(rows)} headers, {blank} unmapped. Fill the field column, then run:")
        print(f"  listnorm clean {' '.join(map(str, args.files))} --mapping {args.out}")
        return 0

    use_comps = bool(args.comps or args.closed_since or args.zip)
    res = normalize(
        args.files, load_overrides(args.mapping), high=args.outlier_high, low=args.outlier_low
    )
    comps = (
        select_comps(res.clean, args.closed_since, args.zip, not args.keep_flagged)
        if use_comps
        else None
    )
    paths = write_outputs(res, args.out, parquet=not args.no_parquet, comps=comps)
    s = res.summary
    print(f"{s['input_rows']} rows in, {s['clean_rows']} clean rows out")
    print(
        f"{s['duplicates_removed']} duplicate rows merged, {s['changes']} changes kept as history"
    )
    print(
        f"{s['review_items']} review items, {s['outlier_flags']} price-per-sq-ft outliers, "
        f"{s['unmapped_headers']} headers ignored"
    )
    if comps is not None:
        print(f"{len(comps)} closed sales in the comps shortlist")
    for p in paths:
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

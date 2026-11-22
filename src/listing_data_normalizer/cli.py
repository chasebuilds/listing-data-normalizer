"""Command line: listnorm clean FILE [FILE ...] -o OUTDIR"""

from __future__ import annotations

import argparse
from pathlib import Path

from listing_data_normalizer import __version__
from listing_data_normalizer.core import DISCLAIMER, load_overrides, normalize, write_outputs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="listnorm", description=DISCLAIMER)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clean", help="normalize one or more CSV/XLSX exports")
    c.add_argument("files", nargs="+", type=Path, help="first file wins when sources disagree")
    c.add_argument("-o", "--out", type=Path, default=Path("ldn-out"))
    c.add_argument("--mapping", type=Path, help="CSV with columns source_header,field")
    c.add_argument("--no-parquet", action="store_true")
    c.add_argument("--outlier-high", type=float, default=2.0)
    c.add_argument("--outlier-low", type=float, default=0.5)
    args = ap.parse_args(argv)
    res = normalize(
        args.files, load_overrides(args.mapping), high=args.outlier_high, low=args.outlier_low
    )
    paths = write_outputs(res, args.out, parquet=not args.no_parquet)
    s = res.summary
    print(f"{s['input_rows']} rows in, {s['clean_rows']} clean rows out")
    print(
        f"{s['duplicates_removed']} duplicate rows merged, {s['changes']} changes kept as history"
    )
    print(
        f"{s['review_items']} review items, {s['outlier_flags']} price-per-sq-ft outliers, "
        f"{s['unmapped_headers']} headers ignored"
    )
    for p in paths:
        print(f"Wrote {p}")
    return 0

"""End to end: read files, normalize rows, dedupe, flag outliers, write outputs."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from listing_data_normalizer.dedupe import build
from listing_data_normalizer.io import write_csv, write_parquet, write_workbook
from listing_data_normalizer.outliers import flag_outliers
from listing_data_normalizer.pipeline import Result, normalize_files
from listing_data_normalizer.schema import CLEAN_COLUMNS

DUP_COLUMNS = [
    "X_PropertyKey",
    "SourceFile",
    "SourceRow",
    "KeptSourceFile",
    "KeptSourceRow",
    "Reason",
    "Conflicts",
]
CHANGE_COLUMNS = [
    "X_PropertyKey",
    "UnparsedAddress",
    "ChangeType",
    "FromDate",
    "FromStatus",
    "FromPrice",
    "ToDate",
    "ToStatus",
    "ToPrice",
    "PriceChange",
    "PriceChangePct",
    "Days",
]
REVIEW_COLUMNS = ["SourceFile", "SourceRow", "Field", "RawValue", "Reason"]
MAPPING_COLUMNS = [
    "SourceFile",
    "SourceHeader",
    "MappedTo",
    "Method",
    "Confidence",
    "UnitHint",
    "Note",
]
DISCLAIMER = (
    "Analysis and education tool. Not an appraisal. A USPAP-compliant appraisal requires a "
    "licensed or certified appraiser."
)


def load_overrides(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return {r["source_header"]: r["field"] for r in csv.DictReader(fh)}


def normalize(
    paths: list[Path],
    overrides: dict[str, str] | None = None,
    today: date | None = None,
    high: float = 2.0,
    low: float = 0.5,
) -> Result:
    res = normalize_files(paths, overrides, today)
    priority = {p.name: i for i, p in enumerate(paths)}
    res.clean, res.duplicates, res.changes, res.clusters = build(res.records, priority)
    flag_outliers(res.clean, high, low)
    for r in res.clean:
        r["X_Flags"] = ", ".join(dict.fromkeys(r["_flags"]))
    res.summary = {
        "input_rows": len(res.records),
        "clean_rows": len(res.clean),
        "duplicates_removed": len(res.duplicates),
        "changes": len(res.changes),
        "review_items": len(res.review),
        "outlier_flags": sum(1 for r in res.clean if "PPSF" in r["X_Flags"]),
        "unmapped_headers": sum(1 for m in res.mapping if not m.field),
    }
    return res


def write_outputs(res: Result, outdir: Path, parquet: bool = True) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    review = [
        {
            "SourceFile": i.source,
            "SourceRow": i.row,
            "Field": i.field,
            "RawValue": i.raw,
            "Reason": i.reason,
        }
        for i in res.review
    ]
    mapping = [
        {
            "SourceFile": m.source,
            "SourceHeader": m.header,
            "MappedTo": m.field or "(ignored)",
            "Method": m.method,
            "Confidence": m.confidence,
            "UnitHint": m.unit_hint,
            "Note": m.note,
        }
        for m in res.mapping
    ]
    written = [outdir / "clean.csv"]
    write_csv(written[0], CLEAN_COLUMNS, res.clean)
    if parquet:
        written.append(outdir / "clean.parquet")
        write_parquet(written[1], CLEAN_COLUMNS, res.clean)
    book = outdir / "listings.xlsx"
    write_workbook(
        book,
        {
            "Clean": (CLEAN_COLUMNS, res.clean),
            "Review": (REVIEW_COLUMNS, review),
            "Duplicates": (DUP_COLUMNS, res.duplicates),
            "Changes": (CHANGE_COLUMNS, res.changes),
            "Mapping": (MAPPING_COLUMNS, mapping),
            "About": (["Note"], [{"Note": DISCLAIMER}]),
        },
    )
    return [*written, book]

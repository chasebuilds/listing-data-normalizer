"""Read CSV or Excel exports, write CSV, Parquet and the Excel workbook."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def read_table(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        wb = load_workbook(path, read_only=True, data_only=True)
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
        wb.close()
        if not rows:
            return [], []
        headers = [
            str(h).strip() if h is not None else f"column_{i + 1}" for i, h in enumerate(rows[0])
        ]
        return headers, [dict(zip(headers, r, strict=False)) for r in rows[1:]]
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1252")
    reader = csv.DictReader(text.splitlines())
    headers = [h.strip() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    return headers, [dict(r) for r in reader]


def _cell(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
        return int(v)
    return v


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for r in rows:
            w.writerow(["" if r.get(c) is None else _cell(r.get(c)) for c in columns])


def write_parquet(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    data = {c: [_cell(r.get(c)) for r in rows] for c in columns}
    pq.write_table(pa.table(data), path)


def write_workbook(path: Path, sheets: dict[str, tuple[list[str], list[dict[str, Any]]]]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    head = PatternFill("solid", fgColor="DDE7F0")
    for name, (cols, rows) in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = Font(bold=True), head
        for r in rows:
            ws.append([_cell(r.get(c)) for c in cols])
        ws.freeze_panes = "A2"
        for i, c in enumerate(cols, start=1):
            width = max([len(c)] + [len(str(r.get(c) or "")) for r in rows[:200]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 48)
    wb.save(path)

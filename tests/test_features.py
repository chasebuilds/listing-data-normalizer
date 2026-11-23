import csv
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook

from listing_data_normalizer.cli import main
from listing_data_normalizer.core import (
    load_overrides,
    mapping_template,
    normalize,
    select_comps,
)
from listing_data_normalizer.io import read_table

TODAY = date(2026, 11, 22)


def county_export(tmp_path: Path) -> Path:
    path = tmp_path / "county.csv"
    path.write_text(
        "Pike County Property Report,,,\n"
        "Run date 11/20/2026,,,\n"
        ",,,\n"
        "Parcel,Situs,Sale Price,Sale Date,Sale Price\n"
        "01-1,1 Oak St Town KY 41501,120000,2025-05-06,999\n"
        "01-2,2 Oak St Town KY 41501,130000,2025-06-07,999\n"
        "Total records: 2,,,\n",
        encoding="utf-8",
    )
    return path


def test_header_row_found_below_title_lines(tmp_path: Path) -> None:
    headers, rows, first = read_table(county_export(tmp_path))
    assert headers == ["Parcel", "Situs", "Sale Price", "Sale Date", "Sale Price.2"]
    assert first == 5 and len(rows) == 3  # the footer is still a raw row here


def test_footer_skipped_and_source_row_is_the_sheet_row(tmp_path: Path) -> None:
    res = normalize([county_export(tmp_path)], today=TODAY)
    assert [r["SourceRow"] for r in res.records] == [5, 6]
    assert [r["ClosePrice"] for r in res.records] == [120000.0, 130000.0]
    dup = [m for m in res.mapping if m.header == "Sale Price.2"]
    assert dup and dup[0].field == ""  # the repeated column does not overwrite the first


def test_header_row_below_title_in_excel(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Weekly listing report"])
    ws.append([])
    ws.append(["MLS #", "List Price", "Address", "Status"])
    ws.append(["A1", 150000, "3 Pine Ln, Town, KY 41501", "Active"])
    path = tmp_path / "r.xlsx"
    wb.save(path)
    res = normalize([path], today=TODAY)
    assert res.records[0]["SourceRow"] == 4 and res.records[0]["ListPrice"] == 150000.0


def test_map_command_and_edit_roundtrip(tmp_path: Path, capsys: object) -> None:
    f = tmp_path / "x.csv"
    f.write_text("Address,Prop Cond,Mystery\n1 A St Town KY 41501,Good,zz\n", encoding="utf-8")
    out = tmp_path / "mapping.csv"
    assert main(["map", str(f), "-o", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    by = {r["source_header"]: r for r in rows}
    assert by["Address"]["field"] == "Address" and by["Address"]["method"] == "exact"
    assert by["Mystery"]["field"] == ""
    assert load_overrides(out) == {"Address": "Address", "Prop Cond": "PropertyCondition"} or (
        "Mystery" not in load_overrides(out)
    )
    # fill one blank, run clean with the edited file
    text = out.read_text(encoding="utf-8").replace("Mystery,,", "Mystery,YearBuilt,")
    out.write_text(text, encoding="utf-8")
    assert load_overrides(out)["Mystery"] == "YearBuilt"
    assert mapping_template([f], load_overrides(out))[2]["method"] == "override"


def sales(tmp_path: Path) -> Path:
    rows = []
    for i in range(12):
        price = 150000 if i != 11 else 900000
        rows.append(
            {
                "Address": f"{i + 1} Pine Ln, Town, KY {41501 if i % 2 else 41502}",
                "Sold Price": price,
                "Sold Date": f"2025-0{1 + i % 9}-10",
                "SqFt": 1500,
            }
        )
    path = tmp_path / "sales.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def test_select_comps_filters(tmp_path: Path) -> None:
    res = normalize([sales(tmp_path)], today=TODAY)
    everything = select_comps(res.clean, exclude_flagged=False)
    assert len(everything) == 12
    kept = select_comps(res.clean)
    assert len(kept) == 11 and all(r["StreetNumber"] != "12" for r in kept)  # outlier dropped
    recent = select_comps(res.clean, closed_since=date(2025, 6, 1), exclude_flagged=False)
    assert all(r["CloseDate"] >= date(2025, 6, 1) for r in recent)
    only = select_comps(res.clean, postal_codes=["41501"], exclude_flagged=False)
    assert only and all(r["PostalCode"] == "41501" for r in only)
    dates = [r["CloseDate"] for r in kept]
    assert dates == sorted(dates, reverse=True)


def test_comps_needs_price_and_area(tmp_path: Path) -> None:
    f = tmp_path / "l.csv"
    f.write_text(
        "Address,List Price,SqFt,Sold Price\n1 A St Town KY 41501,100000,1000,\n"
        "2 A St Town KY 41501,,1000,90000\n3 A St Town KY 41501,,,90000\n",
        encoding="utf-8",
    )
    res = normalize([f], today=TODAY)
    assert [r["StreetNumber"] for r in select_comps(res.clean)] == ["2"]


def test_cli_comps_output(tmp_path: Path) -> None:
    out = tmp_path / "out"
    code = main(
        [
            "clean",
            str(sales(tmp_path)),
            "-o",
            str(out),
            "--no-parquet",
            "--closed-since",
            "2025-01-01",
            "--zip",
            "41501",
        ]
    )
    assert code == 0 and (out / "comps.csv").exists()
    wb = load_workbook(out / "listings.xlsx")
    assert "Comps" in wb.sheetnames
    rows = list(csv.DictReader((out / "comps.csv").open(encoding="utf-8")))
    assert rows and {r["X_PropertyKey"].split("|")[-1] for r in rows} == {"41501"}

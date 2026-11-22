import csv
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from listing_data_normalizer.cli import main
from listing_data_normalizer.core import load_overrides, normalize, write_outputs

TODAY = date(2026, 11, 22)


def write(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def mls(tmp_path: Path) -> Path:
    return write(
        tmp_path / "mls.csv",
        [
            {
                "MLS #": "100",
                "Status": "Active",
                "List Price": "$200,000",
                "List Date": "1/5/2025",
                "Sold Price": "",
                "Sold Date": "",
                "Address": "12 Oak Street Apt 3",
                "City": "Harlow Creek",
                "St": "KY",
                "Zip": "41501",
                "Beds/Baths": "3/2.5",
                "SqFt": "1,500",
                "Lot": "0.25 ac",
                "Yr Built": "c. 1980",
                "Condition": "Needs TLC",
            },
            {
                "MLS #": "100",
                "Status": "Active",
                "List Price": "$190,000",
                "List Date": "2/10/2025",
                "Sold Price": "",
                "Sold Date": "",
                "Address": "12 OAK ST #3",
                "City": "HARLOW CREEK",
                "St": "Kentucky",
                "Zip": "41501-1234",
                "Beds/Baths": "3/2.5",
                "SqFt": "1500",
                "Lot": "10890 sf",
                "Yr Built": "1980",
                "Condition": "Fair",
            },
            {
                "MLS #": "100",
                "Status": "Sold",
                "List Price": "$190,000",
                "List Date": "1/5/2025",
                "Sold Price": "$185,000",
                "Sold Date": "3/20/2025",
                "Address": "12 Oak St Unit 3",
                "City": "Harlow Creek",
                "St": "KY",
                "Zip": "41501",
                "Beds/Baths": "3/2.5",
                "SqFt": "1,500",
                "Lot": "0.25 ac",
                "Yr Built": "1980",
                "Condition": "Fair",
            },
        ],
    )


def assessor(tmp_path: Path) -> Path:
    return write(
        tmp_path / "assessor.csv",
        [
            {
                "PARCEL_ID": "01-02-003",
                "SITUS": "12 OAK ST UNIT 3",
                "SITUS_CITY": "HARLOW CREEK",
                "STATE": "KY",
                "ZIP": "41501",
                "BLDG_SQFT": "1600",
                "LAST_SALE_PRICE": "185000",
                "LAST_SALE_DATE": "2025-03-22",
                "COND_CD": "F",
            },
            {
                "PARCEL_ID": "99-99-999",
                "SITUS": "5 Elm Rd",
                "SITUS_CITY": "Harlow Creek",
                "STATE": "KY",
                "ZIP": "41501",
                "BLDG_SQFT": "1200",
                "LAST_SALE_PRICE": "",
                "LAST_SALE_DATE": "",
                "COND_CD": "G",
            },
        ],
    )


def test_end_to_end(tmp_path: Path) -> None:
    res = normalize([mls(tmp_path), assessor(tmp_path)], today=TODAY)
    assert res.summary["input_rows"] == 5
    # three events for 12 Oak St (list, price cut, sale) plus the attribute-only Elm Rd row
    keys = {r["X_PropertyKey"] for r in res.clean}
    assert keys == {"12||OAK|ST||3|41501", "5||ELM|RD|||41501"}
    oak = [r for r in res.clean if r["X_PropertyKey"].startswith("12")]
    assert len(oak) == 3
    sale = next(r for r in oak if r.get("ClosePrice"))
    assert sale["X_SourceCount"] == 2 and sale["X_Sources"] == "mls.csv, assessor.csv"
    assert sale["ParcelNumber"] == "0102003"
    assert sale["BathroomsFull"] == 2 and sale["BathroomsHalf"] == 1
    assert sale["BathroomsTotalInteger"] == 3
    assert sale["PropertyCondition"] == "Fair"
    assert "FIELD_CONFLICT" in sale["X_Flags"]  # 1,500 vs 1,600 sq ft
    assert len(res.duplicates) == 1


def test_changes_history(tmp_path: Path) -> None:
    res = normalize([mls(tmp_path), assessor(tmp_path)], today=TODAY)
    kinds = [c["ChangeType"] for c in res.changes]
    assert kinds == ["List price change", "Sold after listing"]
    cut = res.changes[0]
    assert cut["PriceChange"] == -10000 and cut["PriceChangePct"] == -5.0 and cut["Days"] == 36
    assert res.changes[1]["PriceChange"] == -5000


def test_attribute_only_row_stands_alone_without_events(tmp_path: Path) -> None:
    res = normalize([assessor(tmp_path)], today=TODAY)
    elm = next(r for r in res.clean if r["StreetName"] == "ELM")
    assert elm["X_SourceCount"] == 1 and elm.get("ClosePrice") is None


def test_review_and_mapping(tmp_path: Path) -> None:
    f = write(
        tmp_path / "bad.csv",
        [
            {
                "Address": "Main St",
                "List Price": "call agent",
                "Yr Built": "85",
                "Mystery": "x",
                "Condition": "see remarks",
            },
            {
                "Address": "1 Main St",
                "List Price": "$5",
                "Yr Built": "1990",
                "Mystery": "x",
                "Condition": "Good",
            },
        ],
    )
    res = normalize([f], today=TODAY)
    reasons = " | ".join(i.reason for i in res.review)
    assert "no house number" in reasons and "could not read price" in reasons
    assert "could not read year built" in reasons and "unrecognized condition" in reasons
    assert "under $1,000" in reasons
    mystery = next(m for m in res.mapping if m.header == "Mystery")
    assert mystery.method == "unmapped"


def test_outliers_flagged(tmp_path: Path) -> None:
    rows = []
    for i in range(12):
        price = 150000 if i != 11 else 900000
        rows.append(
            {
                "Address": f"{i + 1} Pine Ln, Town, KY 41501",
                "List Price": price,
                "SqFt": 1500,
                "MLS #": f"A{i}",
                "List Date": "2025-01-01",
            }
        )
    res = normalize([write(tmp_path / "o.csv", rows)], today=TODAY)
    flagged = [r["StreetNumber"] for r in res.clean if "PPSF_HIGH" in r["X_Flags"]]
    assert flagged == ["12"]
    assert all("PPSF" not in r["X_Flags"] for r in res.clean if r["StreetNumber"] != "12")


def test_metric_area_header(tmp_path: Path) -> None:
    f = write(
        tmp_path / "metric.csv",
        [{"Address": "1 A St, Town, KY 41501", "GLA (m2)": "139.35", "Acreage": "2"}],
    )
    res = normalize([f], today=TODAY)
    assert abs(res.clean[0]["LivingArea"] - 1500) < 1
    assert res.clean[0]["LotSizeAcres"] == 2.0 and res.clean[0]["LotSizeSquareFeet"] == 87120


def test_mapping_override_file(tmp_path: Path) -> None:
    m = tmp_path / "map.csv"
    m.write_text("source_header,field\nWeird Col,YearBuilt\n", encoding="utf-8")
    f = write(tmp_path / "w.csv", [{"Address": "1 A St, Town, KY 41501", "Weird Col": "1999"}])
    res = normalize([f], load_overrides(m), today=TODAY)
    assert res.clean[0]["YearBuilt"] == 1999


def test_outputs_and_cli(tmp_path: Path, capsys: object) -> None:
    out = tmp_path / "out"
    code = main(["clean", str(mls(tmp_path)), str(assessor(tmp_path)), "-o", str(out)])
    assert code == 0
    assert {p.name for p in out.iterdir()} == {"clean.csv", "clean.parquet", "listings.xlsx"}
    wb = load_workbook(out / "listings.xlsx")
    assert wb.sheetnames == ["Clean", "Review", "Duplicates", "Changes", "Mapping", "About"]
    assert "USPAP" in wb["About"]["A2"].value
    import pyarrow.parquet as pq

    assert pq.read_table(out / "clean.parquet").num_rows == 4
    res = normalize([mls(tmp_path)], today=TODAY)
    assert write_outputs(res, tmp_path / "o2", parquet=False)[0].name == "clean.csv"


def test_excel_input(tmp_path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Addr", "Bed/Bath", "Sale $", "Sale Date"])
    ws.append(["1 A St, Town, KY 41501", "3 BR 2 BA", 120000, date(2025, 5, 6)])
    ws.append(["2 A St, Town, KY 41501", "3/2", "$130K", 45720])
    path = tmp_path / "comps.xlsx"
    wb.save(path)
    res = normalize([path], today=TODAY)
    assert [r["ClosePrice"] for r in res.clean] == [120000.0, 130000.0]
    assert [r["CloseDate"] for r in res.clean] == [date(2025, 5, 6), date(2025, 3, 4)]
    assert res.clean[0]["StandardStatus"] == "Closed"

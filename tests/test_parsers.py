from datetime import date

import pytest

from listing_data_normalizer import parsers as p

TODAY = date(2026, 11, 22)


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("$249,900", 249900.0),
        ("249900", 249900.0),
        ("249,900.00", 249900.0),
        ("$249.9K", 249900.0),
        ("1.2M", 1200000.0),
        ("1.2 million", 1200000.0),
        (250000, 250000.0),
    ],
)
def test_price(raw: object, want: float) -> None:
    assert p.parse_price(raw) == (want, None)


@pytest.mark.parametrize("raw", ["call agent", "$$$", "see remarks"])
def test_price_junk(raw: str) -> None:
    value, issue = p.parse_price(raw)
    assert value is None and issue


def test_price_nominal_and_blank() -> None:
    value, issue = p.parse_price("$1")
    assert value is None and issue
    assert p.parse_price("N/A") == (None, None)
    assert p.parse_price("") == (None, None)


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("2025-03-04", date(2025, 3, 4)),
        ("03/04/2025", date(2025, 3, 4)),
        ("3/4/25", date(2025, 3, 4)),
        ("Mar 4, 2025", date(2025, 3, 4)),
        ("04-Mar-25", date(2025, 3, 4)),
        ("20250304", date(2025, 3, 4)),
        ("March 4th, 2025", date(2025, 3, 4)),
        ("25/03/2025", date(2025, 3, 25)),
        ("2025-03-04 10:15:00", date(2025, 3, 4)),
        ("45720", date(2025, 3, 4)),
    ],
)
def test_dates(raw: str, want: date) -> None:
    assert p.parse_date(raw, TODAY) == (want, None)


def test_dates_bad() -> None:
    assert p.parse_date("soon", TODAY)[1]
    assert p.parse_date("2031-01-01", TODAY)[0] is None


@pytest.mark.parametrize(
    ("raw", "hint", "want"),
    [
        ("1,850", None, 1850.0),
        ("1850 sq ft", None, 1850.0),
        ("1850 SF", "sqm", 1850.0),
        ("172 sq m", None, 1851.4),
        ("172", "sqm", 1851.4),
        ("172.0 m2", None, 1851.4),
    ],
)
def test_area(raw: str, hint: str | None, want: float) -> None:
    assert p.parse_area(raw, hint)[0] == pytest.approx(want, abs=0.2)


def test_area_bare_small_is_flagged() -> None:
    value, issue = p.parse_area("150")
    assert value == 150.0 and issue


@pytest.mark.parametrize(
    ("raw", "hint", "want"),
    [
        ("0.25 ac", None, 0.25),
        ("10,890 sqft", None, 0.25),
        ("2.5 acres", None, 2.5),
        ("0.25", "acre", 0.25),
        ("10890", None, 0.25),
        ("75x145", None, 0.2497),
        ("1 ha", None, 2.4711),
        ("4047 sq m", None, 1.0),
    ],
)
def test_lot(raw: str, hint: str | None, want: float) -> None:
    assert p.parse_lot(raw, hint)[0] == pytest.approx(want, abs=0.001)


def test_lot_bare_is_flagged() -> None:
    assert p.parse_lot("0.25")[1]


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("3/2.5", (3, 2, 1)),
        ("3 BR 2 BA", (3, 2, 0)),
        ("3bd/2.5ba", (3, 2, 1)),
        ("3 bed 2 full 1 half", (3, 2, 1)),
        ("3/2/1", (3, 2, 1)),
        ("4 beds, 3 baths", (4, 3, 0)),
        ("3BR/2 1/2 BA", (3, 2, 1)),
        ("Studio", (0, None, None)),
        ("2/1", (2, 1, 0)),
    ],
)
def test_bedbath(raw: str, want: tuple[int, int | None, int | None]) -> None:
    vals, _ = p.parse_bedbath(raw)
    assert (vals["beds"], vals["full"], vals["half"]) == want


def test_bedbath_junk() -> None:
    vals, issues = p.parse_bedbath("TBD-ish")
    assert vals["beds"] is None and issues


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("2.5", (2, 1)),
        ("2", (2, 0)),
        ("2 full, 1 half", (2, 1)),
        ("2 1/2 baths", (2, 1)),
        ("3 baths", (3, 0)),
    ],
)
def test_bath_total(raw: str, want: tuple[int, int]) -> None:
    assert p.parse_bath_total(raw)[0] == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("1998", 1998),
        ("c. 1950", 1950),
        ("circa 1950", 1950),
        ("Built in 2003", 2003),
        (1987.0, 1987),
        ("1950s", 1950),
    ],
)
def test_year(raw: object, want: int) -> None:
    assert p.parse_year_built(raw, 2026)[0] == want


@pytest.mark.parametrize("raw", ["New construction", "85", "unknown?", "2099", "1500"])
def test_year_review(raw: str) -> None:
    assert p.parse_year_built(raw, 2026)[0] is None


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("Excellent", "Excellent"),
        ("Like new", "Excellent"),
        ("Well maintained", "Good"),
        ("Typical for age", "Average"),
        ("avg", "Average"),
        ("Dated, needs updating", "Fair"),
        ("Fair to good", "Fair"),
        ("Fixer upper", "Poor"),
        ("Sold as-is", "Poor"),
        ("E", "Excellent"),
        ("F", "Fair"),
        ("below average", "Fair"),
    ],
)
def test_condition(raw: str, want: str) -> None:
    assert p.parse_condition(raw) == (want, None)


def test_condition_unknown() -> None:
    assert p.parse_condition("see remarks")[0] is None


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("A", "Active"),
        ("Sold", "Closed"),
        ("exp", "Expired"),
        ("Pend", "Pending"),
        ("Under Contract", "Active Under Contract"),
        ("Cancelled", "Canceled"),
        ("W", "Withdrawn"),
    ],
)
def test_status(raw: str, want: str) -> None:
    assert p.parse_status(raw) == (want, None)


def test_subtype() -> None:
    assert p.parse_subtype("Condo")[0] == "Condominium"
    assert p.parse_subtype("Mobile Home")[0] == "Manufactured Home"
    assert p.parse_subtype("Ranch")[0] == "Single Family Residence"

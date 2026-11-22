from listing_data_normalizer import address as a
from listing_data_normalizer.headers import map_headers


def test_street_variants_match() -> None:
    lines = set()
    for t in ["123 N Main Street Apt 4B", "123 north main st #4b", "123 N. MAIN ST., UNIT 4B"]:
        st, why = a.parse_street(t)
        assert st and not why
        lines.add(st.line())
    assert lines == {"123 N MAIN ST # 4B"}


def test_route_and_no_suffix() -> None:
    st, _ = a.parse_street("9098 Highway 426")
    assert st and st.name == "HWY 426" and st.suffix == ""


def test_name_with_unit_lookalike() -> None:
    st, _ = a.parse_street("12 Oak Unity")
    assert st and st.unit == "" and st.name == "OAK UNITY"


def test_no_house_number() -> None:
    assert a.parse_street("Main St")[0] is None


def test_split_full() -> None:
    assert a.split_full_address("12 Oak St, Harlow Creek, KY 41501") == (
        "12 Oak St",
        "Harlow Creek",
        "KY",
        "41501",
    )
    assert a.split_full_address("12 Oak St, Apt 4")[0] == "12 Oak St Apt 4"
    assert a.split_full_address("12 Oak St KY 41501")[2:] == ("KY", "41501")


def test_state_zip() -> None:
    assert a.norm_state("Kentucky") == ("KY", None)
    assert a.norm_state("ky")[0] == "KY"
    assert a.norm_zip(4101)[0] == "04101"
    assert a.norm_zip("41501.0")[0] == "41501"
    assert a.norm_zip("415011234")[0] == "41501-1234"


def test_headers() -> None:
    cols = [
        "MLS #",
        "Sq Ft",
        "Sale $",
        "Bed/Bath",
        "Lot Size (acres)",
        "Bedroms",
        "Notes",
        "Yr Built",
    ]
    got = {m.header: m for m in map_headers("x.csv", cols)}
    assert got["MLS #"].field == "ListingId"
    assert got["Sq Ft"].field == "LivingArea"
    gla = map_headers("y.csv", ["GLA (m2)"])[0]
    assert gla.field == "LivingArea" and gla.unit_hint == "sqm"
    assert got["Sale $"].field == "ClosePrice"
    assert got["Bed/Bath"].field == "BedBath"
    assert got["Lot Size (acres)"].unit_hint == "acre"
    assert got["Bedroms"].method == "fuzzy" and got["Bedroms"].field == "BedroomsTotal"
    assert got["Notes"].field == "" and got["Notes"].method == "unmapped"


def test_header_override_and_duplicate_target() -> None:
    got = map_headers("x.csv", ["Weird", "Baths", "Bathrooms"], {"Weird": "YearBuilt"})
    assert got[0].field == "YearBuilt" and got[0].method == "override"
    assert got[1].field == "BathroomsTotal" and got[2].method == "duplicate"

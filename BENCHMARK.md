# Benchmark

Written by `benchmark/run_benchmark.py` on 2026-11-23 from a real run.
No number on this page was typed by hand.

Command: `python -m benchmark.run_benchmark --seed 20261122 --properties 3000`
Python 3.11.15 on Windows.
Normalizing all 12,269 rows from 4 files took 1.82 s.

## Method

1. Invent 3,000 fake houses: made-up streets and towns, real state code, price per sq ft that depends on town and condition, 1 to 4 events each (an expired listing, a listing, a price cut, a sale). About 3% are priced 2.8x to 5x above or below their town on purpose.
2. Write them out the way four systems would: two MLS-style exports with different headers (one in square meters, one repeating some rows), a county assessor report with title lines and a footer (last sale only, some units dropped, areas that disagree by up to 5%), and a spreadsheet comps list in Excel (sales only, `3/2.5` style bed/bath, dates as real dates, text and serial numbers).
3. Mess up every field: price as `$249,900`, `249.9K` or `249,900.00`; seven date formats; lot as acres, sq ft or bare; baths as `2.5`, `2 full, 1 half` or `2 1/2 baths`; free-text condition; suffixes spelled or abbreviated; units as `Apt 4`, `#4`, `Unit 4`. About 2% of some fields get junk (`call agent`, `see remarks`) that should be left blank and flagged.
4. Score each normalized row, before duplicates are merged, against the answer for that row. A field counts only when the row's source had a usable value. The score is exact, except living area (within 1 sq ft) and lot acres (within 0.006).
5. Duplicates: every pair of rows describing the same listing or sale of the same house is a true pair. A pair is found when both rows end in the same merged row.
6. Outliers: a merged row is truly off-market when its house's real price per sq ft is more than 2x or less than half the median of its ZIP (this includes about 3% priced that way on purpose and some poor-condition houses). It is found when it carries a PPSF_HIGH or PPSF_LOW flag.

## Result

<!-- benchmark:start -->
| Measure | Result |
|---|---:|
| Rows in (4 files, 3,000 fake houses) | 12,269 |
| Headers mapped to the right RESO field | **100.0%** (56 of 56) |
| Fields right, exact (rows where the source had a value) | **100.0%** (159,352 of 159,352) |
| Rows with every scored field right | 100.0% |
| Junk values left blank | 100.0% (717 of 717) |
| Junk rows flagged in Review | 100.0% |
| Duplicate pairs found (recall) | **98.8%** (6,773 of 6,855) |
| Duplicate pairs that were right (precision) | **98.4%** (6,773 of 6,885) |
| Merged rows that match one true event exactly | 85.3% |
| Off-market rows found (recall) | **78.0%** (163 of 209) |
| Of those, rows priced off-market on purpose that were found | 85.8% (133 of 155) |
| Outlier flags that were right (precision) | **62.5%** (163 of 261) |
<!-- benchmark:end -->

## Field accuracy

| Field | Right | Of | Wrong or left blank | Value where none was due |
|---|---:|---:|---:|---:|
| UnparsedAddress | 100.0% | 12,269 | 0 | 0 |
| PostalCode | 100.0% | 12,269 | 0 | 0 |
| BedroomsTotal | 100.0% | 11,988 | 0 | 0 |
| BathroomsFull | 100.0% | 12,132 | 0 | 0 |
| BathroomsHalf | 100.0% | 12,132 | 0 | 0 |
| LivingArea | 100.0% | 12,021 | 0 | 0 |
| LotSizeAcres | 100.0% | 12,269 | 0 | 0 |
| YearBuilt | 100.0% | 12,142 | 0 | 0 |
| PropertyCondition | 100.0% | 11,484 | 0 | 0 |
| ListPrice | 100.0% | 8,307 | 0 | 0 |
| ClosePrice | 100.0% | 5,547 | 0 | 0 |
| ListingContractDate | 100.0% | 8,432 | 0 | 0 |
| CloseDate | 100.0% | 5,547 | 0 | 0 |
| StandardStatus | 100.0% | 11,381 | 0 | 0 |
| ListingId | 100.0% | 8,432 | 0 | 0 |
| ParcelNumber | 100.0% | 3,000 | 0 | 0 |

## Examples of misses

None in this run.

## What the misses are

Read the examples above (if any) against [LIMITATIONS.md](LIMITATIONS.md). The data is invented by the same author who wrote the parsers, so field accuracy here is a regression guard, not a promise: a real export will have formats this generator never thought of, and those go to the Review sheet.

Duplicate misses come mostly from a source that dropped the unit number and had no parcel to link the rows, and from listings whose price was junk. Outlier misses and false flags come from list and sale prices that differ from the real price per sq ft, and from comparing by subdivision when one source gives it and another does not.

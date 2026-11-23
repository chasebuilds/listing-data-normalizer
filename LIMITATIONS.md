# Limitations

What listing-data-normalizer does not do, or does poorly. Read this before trusting a cleaned file.

## It is not an appraisal tool

- **Nothing here estimates value.** The tool cleans and merges data. A USPAP-compliant appraisal
  requires a licensed or certified appraiser, who must verify the data and choose the comparables.
- **Outlier flags are a prompt to look, not a verdict.** A poor-condition house can really sell at
  half the neighborhood price. The tool flags it and does not remove it.

## Benchmark scope

- **The benchmark data is invented by the same author who wrote the parsers.** Field accuracy near
  100% on it shows the code does what its author expected, not that it reads every real export.
  Real exports have headers, formats and typos the generator never made.

## Headers and values

- **Header mapping is a synonym table plus fuzzy spelling.** An unknown header is ignored and listed
  in the Mapping sheet. Two columns that map to the same field: the first wins, the second is
  ignored (also listed). Supply `--mapping` to fix either.
- **Bare numbers need a guess.** An area with no unit is taken as sq ft (flagged when under 400). A
  lot with no unit is taken as acres at 200 or less and sq ft above that (always flagged). A
  header such as `GLA (m2)` or `Lot Acres` removes the guess.
- **Dates are month first.** `03/04/2025` is March 4. A first number above 12 is read as day first.
  Two-digit years follow Python's rule (00 to 68 is 2000s).
- **Bed/bath with three numbers is beds/full/half.** `3/2/1` is read that way. A `.75` or `.25` bath
  is counted as one half bath and flagged.
- **Year built:** a decade (`1950s`) uses its first year and is flagged. A two-digit year and "new
  construction" are left blank and sent to Review.
- **Condition, status and property type use short word lists.** Unknown text is left blank and sent
  to Review. The values written (`Excellent`, `Good`, `Average`, `Fair`, `Poor`; status names;
  subtype names) are this tool's own simplified sets that echo RESO naming where it exists. They
  are not copies of any MLS's lookup list, and the five condition grades are not a RESO lookup.
  Check them against your MLS before loading the output into one.
- **Prices under $1,000 are treated as errors** (nominal $1 transfers, typos) and left blank.

- **The header row is found by looking in the first 25 rows** for one with at least 3 known
  headers. A report whose real header uses only unusual names is read from its first non-empty
  row instead; use `listnorm map` and `--mapping` to fix that. Only the first sheet of an Excel
  file is read. A one-cell row containing the word total, page or records is skipped as a footer.

## Addresses

- **No geocoding, no USPS lookup.** A clean-looking address for a street that does not exist comes
  out clean. ZIP and state are not checked against each other.
- **No fuzzy address matching.** `Quillon` and `Quilon` are different streets. A source that drops
  the unit number, writes `Fifth` where another writes `5th`, or spells a street differently will
  not link to the others unless a parcel number matches. That is the main duplicate miss in the
  benchmark.
- **Not handled:** rural routes (`RR 2 Box 5`), PO boxes, military addresses, fractional house
  numbers (`12 1/2`), two addresses in one cell. Street names are not spell-corrected.
- **A unit is written `# 4B` in `UnparsedAddress`** whatever the source called it (`Apt`, `Unit`,
  `Ste`). `UnitNumber` holds `4B`.

## Duplicates and history

- **A duplicate is the same property with the same event:** same close price and close date within
  3 days (a sale), or same list price and list date within 3 days (a listing). Anything else at the
  same property is kept as a separate event and shows up in Changes.
- **History needs a date on every row.** A price change exported as a second row must carry its own
  date in the list-date column. Two rows for one listing with the same date and different prices
  cannot be put in order.
- **A row with no price at all** (assessor record with no sale) is merged into the event with the
  same listing ID and date, else into the property's latest event, and listed in Duplicates. If the
  property has no events it stays as its own row.
- **When duplicates disagree**, the first file listed wins and the disagreement is written to the
  Conflicts column. Blank fields are filled from the other rows. Property facts (beds, baths,
  area, lot, year) blank on one event are filled from the property's other events and flagged
  `ATTR_FILLED:<field>`. Condition is never filled across events, because it changes.

## Comps shortlist

- **It is a filter, not a selection of comparables.** It keeps closed sales with a price and a
  living area, optionally since a date and in given ZIP codes, and drops flagged rows. It does not
  rank by similarity, adjust prices or pick comparables; that is the appraiser's job.
- **ZIP is the only location filter.** There is no distance or geocoding.

## Outliers

- **The neighborhood is the subdivision if the merged row has one, else the ZIP, else the city.** A
  ZIP can hold very different neighborhoods. Groups with 5 or fewer priced rows are not checked.
- **The default thresholds are 2x and 0.5x of the median** of the other rows in the group
  (`--outlier-high`, `--outlier-low`). They are not tuned to any market.
- **Mixed prices.** The check uses the close price when there is one and the list price otherwise,
  so a list price and a sale price of the same house can land on different sides of a threshold.
- **No outlier checks on anything but price per sq ft** and an implausible-size check (under 300
  or over 15,000 sq ft).

## Output

- **Parquet needs the `parquet` extra** (pyarrow). CSV and Excel do not.
- **Excel sheets are values, not formulas.** The tool never writes a number it cannot trace to a
  source row, but it does not keep the original text next to the clean value; use Review and the
  `SourceFile` and `SourceRow` columns in Duplicates to go back to the source.

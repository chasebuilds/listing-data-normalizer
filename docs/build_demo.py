"""Build the static demo page (frosted glass) from a real run on the sample files."""

from __future__ import annotations

import argparse
import csv
import html
import re
from datetime import date
from pathlib import Path
from typing import Any

from listing_data_normalizer.core import DISCLAIMER, normalize

ROOT = Path(__file__).resolve().parent.parent
FILES = ["mls_a.csv", "mls_b.csv", "county_assessor.csv", "comps_list.xlsx"]
SHOW = [
    "UnparsedAddress",
    "StandardStatus",
    "BedroomsTotal",
    "BathroomsFull",
    "BathroomsHalf",
    "LivingArea",
    "LotSizeAcres",
    "YearBuilt",
    "PropertyCondition",
    "ListPrice",
    "ClosePrice",
    "ListingContractDate",
    "CloseDate",
    "X_PricePerSqFt",
    "X_Flags",
    "X_SourceCount",
]
CSS = """
:root{--wall:#cdb9a3;--wall2:#e9ddcf;--floor:#b89a80;--glow:#fff6e6;--ink:#2a2019;--ink2:rgba(42,32,25,.66);
--glass:rgba(255,250,244,.30);--edge:rgba(255,255,255,.6);--card:rgba(255,252,248,.58);--solid:#2a2019;--solidfg:#fbf5ee;
--me:#e2583a;--warn:#a8670f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--wall:#2a1f19;--wall2:#3b2c22;--floor:#241a14;--glow:#ffb867;
--ink:#f6ece2;--ink2:rgba(246,236,226,.7);--glass:rgba(34,24,18,.4);--edge:rgba(255,255,255,.16);--card:rgba(48,36,28,.6);
--solid:#f6ece2;--solidfg:#2a2019;--me:#ff7a55;--warn:#f0b45a}}
*{box-sizing:border-box}body{margin:0;background:var(--wall);color:var(--ink);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
.room{position:fixed;inset:0;z-index:0;background:radial-gradient(60% 50% at 78% 18%,var(--glow),transparent 70%),
linear-gradient(180deg,var(--wall2) 0%,var(--wall) 62%,var(--floor) 62.2%,var(--floor) 100%)}
.app{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:18px 16px 60px;display:flex;flex-direction:column;gap:14px}
.glass{background:var(--glass);-webkit-backdrop-filter:blur(26px) saturate(150%);backdrop-filter:blur(26px) saturate(150%);
border:1px solid var(--edge);box-shadow:inset 0 1px 0 var(--edge),0 24px 60px -20px rgba(70,40,20,.3)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:7px 8px;border-radius:999px}
.brand{font-weight:600;padding:6px 14px}
.bar button{border:0;border-radius:999px;padding:7px 14px;background:var(--card);color:var(--ink);font:inherit;cursor:pointer}
.bar button[aria-pressed=true]{background:var(--solid);color:var(--solidfg)}
.stage{border-radius:28px;padding:clamp(18px,3vw,30px)}
h1{margin:0 0 4px;font-size:clamp(24px,3.4vw,32px);font-weight:600;letter-spacing:-.025em}
.sub{margin:0 0 14px;color:var(--ink2);max-width:70ch}
.warn{background:var(--card);border-left:4px solid var(--warn);padding:10px 14px;border-radius:12px;margin:0 0 16px}
.scroll{overflow-x:auto;border-radius:14px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{text-align:left;padding:10px;color:var(--ink2);font-weight:500;white-space:nowrap}
td{padding:8px 10px;border-top:1px solid var(--edge);white-space:nowrap}
.panel{display:none}.panel.on{display:block}
.note{color:var(--ink2);font-size:12.5px;margin:8px 0 0}
"""


def table(cols: list[str], rows: list[dict[str, Any]], limit: int = 30) -> str:
    def cell(v: Any) -> str:
        return html.escape("" if v is None else v.isoformat() if isinstance(v, date) else str(v))

    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell(r.get(c))}</td>" for c in cols) + "</tr>" for r in rows[:limit]
    )
    more = (
        f'<p class="note">Showing {min(limit, len(rows))} of {len(rows)} rows.</p>' if rows else ""
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{more}'


def messy_preview(path: Path, n: int = 6) -> str:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))[:n]
    cols = list(rows[0])
    return table(cols, [dict(r) for r in rows], n)


def bench_table() -> str:
    text = (ROOT / "BENCHMARK.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- benchmark:start -->\s*(.*?)\s*<!-- benchmark:end -->", text, re.S)
    rows = [r.strip("| ").split("|") for r in (m.group(1).splitlines() if m else [])[2:]]
    body = "".join(
        f"<tr><td>{html.escape(a.strip())}</td><td>{html.escape(b.strip().strip('*'))}</td></tr>"
        for a, b in rows
    )
    return f'<div class="scroll"><table><thead><tr><th>Measure</th><th>Result</th></tr></thead><tbody>{body}</tbody></table></div>'


def build(out: Path) -> None:
    paths = [ROOT / "samples" / f for f in FILES]
    res = normalize(paths, today=date(2026, 11, 22))
    s = res.summary
    mapping = [
        {
            "File": m.source,
            "Header": m.header,
            "Mapped to": m.field or "(ignored)",
            "How": m.method,
            "Confidence": m.confidence,
        }
        for m in res.mapping
    ]
    panels = {
        "Messy input": messy_preview(paths[0]) + messy_preview(paths[2]),
        "Clean": table(SHOW, res.clean),
        "Mapping": table(["File", "Header", "Mapped to", "How", "Confidence"], mapping, 80),
        "Duplicates": table(
            ["X_PropertyKey", "SourceFile", "SourceRow", "KeptSourceFile", "Reason", "Conflicts"],
            res.duplicates,
        ),
        "Changes": table(
            [
                "UnparsedAddress",
                "ChangeType",
                "FromDate",
                "FromPrice",
                "ToDate",
                "ToPrice",
                "PriceChange",
                "PriceChangePct",
                "Days",
            ],
            res.changes,
        ),
        "Benchmark": bench_table(),
    }
    nav = "".join(
        f'<button data-p="{i}" aria-pressed="{str(i == 0).lower()}">{html.escape(k)}</button>'
        for i, k in enumerate(panels)
    )
    body = "".join(
        f'<section class="panel{" on" if i == 0 else ""}" id="p{i}">{v}</section>'
        for i, v in enumerate(panels.values())
    )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Listing Data Normalizer</title><style>{CSS}</style></head><body>
<div class="room"></div><div class="app">
<nav class="bar glass"><span class="brand">Chase Builds</span>{nav}</nav>
<main class="stage glass"><h1>Listing Data Normalizer</h1>
<p class="sub">{s["input_rows"]} messy rows from four invented exports became {s["clean_rows"]} clean rows
named after the RESO Data Dictionary. {s["duplicates_removed"]} duplicates were merged,
{s["changes"]} price or status changes were kept as history. Every row here is synthetic.</p>
<p class="warn">{html.escape(DISCLAIMER)}</p>{body}</main></div>
<script>document.querySelectorAll('.bar button').forEach(b=>b.addEventListener('click',()=>{{
document.querySelectorAll('.bar button').forEach(x=>x.setAttribute('aria-pressed',x===b));
document.querySelectorAll('.panel').forEach((p,i)=>p.classList.toggle('on',String(i)===b.dataset.p));}}));</script>
<script>(()=>{{const i=['messy','clean','mapping','duplicates','changes','benchmark'].indexOf(location.hash.slice(1));if(i>0)document.querySelectorAll('.bar button')[i].click();}})();</script></body></html>"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    build(ap.parse_args().out)
    print("ok")

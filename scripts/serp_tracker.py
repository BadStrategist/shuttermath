#!/usr/bin/env python3
"""Track Google Search Console positions for ShutterMath's target queries.

Appends one row per query per run to data/serp_track.csv so week-over-week
movement is measurable. Positions are GSC averages over the window ending
two days ago (GSC lag), weighted per page, and reflect Google search only —
not site visits (GoatCounter covers those, separately and privately).

Auth: Application Default Credentials with the webmasters.readonly scope
(`gcloud auth application-default login --scopes=...`); no keys stored here.

Run:  python scripts/serp_tracker.py [--days 28]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import urllib.parse
from pathlib import Path

from google.auth import default
from google.auth.transport.requests import AuthorizedSession

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "serp_track.csv"
SITE = "sc-domain:shuttermath.com"
API = "https://searchconsole.googleapis.com/webmasters/v3"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# query -> the page that should be winning it
TARGETS = {
    "field of view calculator": "/tools/field-of-view.html",
    "field of view chart": "/tools/field-of-view.html",
    "angle of view calculator": "/tools/field-of-view.html",
    "nd filter chart": "/pages/nd-filter-long-exposure-chart.html",
    "nd filter table": "/pages/nd-filter-long-exposure-chart.html",
    "nd filter calculator": "/tools/nd-filter.html",
    "depth of field calculator": "/tools/depth-of-field.html",
    "dof calculator": "/tools/depth-of-field.html",
    "camera sensor size chart": "/pages/camera-sensor-sizes.html",
    "camera sensor sizes": "/pages/camera-sensor-sizes.html",
    "exposure value calculator": "/tools/exposure.html",
    "print resolution": "/tools/print-resolution.html",
    "guide number": "/tools/flash-guide-number.html",
    "shutter angle calculator": "/tools/shutter-angle.html",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28, help="trailing window length (default 28)")
    args = ap.parse_args()

    creds, _ = default(scopes=SCOPES)
    sess = AuthorizedSession(creds)
    end = dt.date.today() - dt.timedelta(days=2)      # GSC lags ~2 days
    start = end - dt.timedelta(days=args.days - 1)

    body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["query", "page"], "rowLimit": 5000}
    url = f"{API}/sites/{urllib.parse.quote(SITE, safe='')}/searchAnalytics/query"
    r = sess.post(url, json=body)
    if r.status_code != 200:
        print(f"GSC error {r.status_code}: {r.text[:400]}", file=sys.stderr)
        return 1
    rows = r.json().get("rows", [])

    print(f"ShutterMath SERP positions — GSC window {start} .. {end} ({args.days} days)")
    print(f"{'query':<30} {'impr':>6} {'clicks':>6} {'pos':>6}  target page")
    out = []
    for q, page in TARGETS.items():
        hits = [x for x in rows if x["keys"][0].lower() == q.lower()]
        imp = sum(x["impressions"] for x in hits)
        clk = sum(x["clicks"] for x in hits)
        pos = (sum(x["position"] * x["impressions"] for x in hits) / imp) if imp else None
        served = max(hits, key=lambda x: x["impressions"])["keys"][1] if hits else ""
        flag = "" if (not served or served.endswith(page)) else "  <- served by " + served.split("shuttermath.com")[-1]
        print(f"{q:<30} {imp:>6} {clk:>6} {('%.1f' % pos) if pos else '   -':>6}  {page}{flag}")
        out.append(dict(date=end.isoformat(), query=q, target_page=page, served_page=served,
                        impressions=imp, clicks=clk,
                        position=(round(pos, 2) if pos else "")))

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        if new:
            w.writeheader()
        w.writerows(out)
    print(f"\nappended {len(out)} rows -> {CSV_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

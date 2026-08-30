#!/usr/bin/env python3
"""Generate llms.txt for ShutterMath from the live sitemap + page titles.

llms.txt is the standard AI-agent discovery file (llmstxt.org). It is built
from REAL data (sitemap.xml URLs + each page's <title>/description) so it
never drifts from the site. Re-run after any content wave.

  python scripts/gen_llms.py [--site https://shuttermath.com] [--out llms.txt]
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "sitemap.xml"
OUT = ROOT / "llms.txt"
SITE = "https://shuttermath.com"

TAGLINE = ("Free photography calculators that use your real camera's sensor. "
           "Depth of field, hyperfocal distance, ND filter exposure, flash "
           "guide number, astro pixel scale, field of view, exposure "
           "equivalence and more - computed from exact sensor dimensions and "
           "textbook formulas, verified against known values. Every tool is "
           "100% free with no sign-up. Includes camera-by-camera guides, "
           "charts and plain-English photography tutorials.")

# Section -> list of URL path prefixes, in display order.
# Claim order matters: a URL matched by an EARLIER section is consumed and
# never re-listed, so the more specific prefix (cameras) must come first.
SECTIONS = [
    ("Tools & Calculators", ("/tools/",)),
    ("Camera Pages", ("/pages/cameras/",)),
    ("Guides & Tutorials", ("/pages/",)),
]

# Specific pages worth surfacing at the top of their section, by URL path.
FEATURED = [
    ("/tools/depth-of-field.html", "Depth of Field Calculator"),
    ("/tools/hyperfocal.html", "Hyperfocal Distance Calculator"),
    ("/tools/nd-filter.html", "ND Filter / Long Exposure Calculator"),
    ("/tools/exposure.html", "Exposure Equivalence Calculator"),
    ("/tools/field-of-view.html", "Field of View Calculator"),
    ("/pages/free-photography-calculators.html", "Free Photography Calculators hub"),
    ("/pages/camera-sensor-sizes.html", "Camera Sensor Sizes explained"),
]


def page_title(url: str) -> str:
    """Extract the real <title> from the built HTML file for a URL."""
    rel = url.removeprefix(SITE).lstrip("/")
    if not rel:
        rel = "index.html"
    p = ROOT / rel
    if p.is_dir():
        p = p / "index.html"
    if not p.exists():
        return None
    m = re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())
    # strip the site-name suffix — noise for an AI consumer and it hides
    # truncated titles in the source HTML ("... | Shut…")
    title = re.sub(r"\s*\|\s*Shut.*?$", "", title, flags=re.I).strip()
    return title or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    if not SITEMAP.exists():
        print(f"missing {SITEMAP}", file=sys.stderr)
        return 1

    urls = re.findall(r"<loc>(.*?)</loc>", SITEMAP.read_text(encoding="utf-8"))
    urls = [u for u in urls if u.startswith(args.site)]
    print(f"parsed {len(urls)} URLs from sitemap")

    lines = ["# ShutterMath", "", f"> {TAGLINE}", "",
             "ShutterMath is a free, ad-supported suite of photography "
             "calculators and guides. Everything runs in the browser, "
             "calculations use exact sensor sizes and verified optical "
             "formulas, and no account is required.",
             "", "## Key Facts", "",
             "- Free, no sign-up, no limits; tools are `isAccessibleForFree`.",
             "- Sensor database covers 30+ real cameras (mirrorless, DSLR, phones) with exact sensor dimensions.",
             "- Formulas validated against textbook values (DoF, hyperfocal, ND, guide number, pixel scale).",
             "- Owned by a small independent publisher; supported by ads shown only after consent.",
             ""]

    claimed = set()

    for section, prefixes in SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        section_urls = []
        for u in urls:
            # only list URLs not yet claimed by an earlier section
            if u in claimed:
                continue
            if any(u[len(args.site):].startswith(p) for p in prefixes):
                section_urls.append(u)
        # featured first (dedup), then everything else in sitemap order
        ordered = []
        for fu in FEATURED:
            if fu in section_urls and fu not in ordered:
                ordered.append(fu)
        for u in section_urls:
            if u not in ordered:
                ordered.append(u)
        for u in ordered:
            claimed.add(u)
            title = page_title(u)
            if not title:
                title = u.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            lines.append(f"- [{title}]({u})")
        lines.append("")

    # anything not covered by the sections (home, trust pages)
    covered = set()
    for _, prefixes in SECTIONS:
        for u in urls:
            if any(u[len(args.site):].startswith(p) for p in prefixes):
                covered.add(u)
    misc = [u for u in urls if u not in covered]
    if misc:
        lines.append("## Site")
        lines.append("")
        for u in misc:
            title = page_title(u) or u
            lines.append(f"- [{title}]({u})")
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines, {len(urls)} URLs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

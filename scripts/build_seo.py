"""Add crawl/AI-answer metadata to every page: favicon, Organization + BreadcrumbList
JSON-LD, og:url, robots directives, and a dateModified. Idempotent (marker-delimited block).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = r"C:\Users\tscac\Projects\_archive\shuttermath"
DOMAIN = "https://shuttermath.com"
START = "<!-- SEO:LINKS:START -->"
END = "<!-- SEO:LINKS:END -->"

SECTIONS = {
    "/tools": ("Calculators", "/tools/index.html"),
    "/pages": ("Guides", "/pages/guides.html"),
}

PRETTY = {
    "tools": "Calculators",
    "pages": "Guides",
    "cameras": "Cameras",
}

FAVICON = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='7' fill='%232563eb'/%3E"
    "%3Ctext x='16' y='23' font-family='Georgia,serif' font-size='20' font-weight='700'"
    " fill='%23fff' text-anchor='middle'%3ES%3C/text%3E%3C/svg%3E\">"
)


def url_of(rel):
    return DOMAIN + ("/" if rel == "/index.html" else rel)


def pretty(seg):
    if seg.endswith(".html"):
        seg = seg[:-5]
    return PRETTY.get(seg, seg.replace("-", " ").title())


def crumbs_for(rel):
    items = [("Home", DOMAIN + "/")]
    if rel == "/index.html":
        return items
    parts = [p for p in rel.strip("/").split("/") if p]
    if len(parts) == 1:
        items.append((pretty(parts[0]), DOMAIN + rel))
        return items
    first = "/" + parts[0]
    if first in SECTIONS:
        items.append(SECTIONS[first])
    else:
        items.append((parts[0].replace("-", " ").title(), DOMAIN + first + "/index.html"))
    for i in range(1, len(parts) - 1):
        sub = "/" + "/".join(parts[: i + 1])
        items.append((parts[i].replace("-", " ").title(), DOMAIN + sub + "/index.html"))
    items.append((pretty(parts[-1]), DOMAIN + rel))
    return items


def graph(rel, title, date_mod):
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": DOMAIN + "/#organization",
                "name": "ShutterMath",
                "url": DOMAIN + "/",
                "logo": DOMAIN + "/assets/img/og.png",
                "description": "Free, sensor-accurate photography calculators and reference charts for depth of field, hyperfocal distance, exposure, ND filters, field of view and video shutter angle.",
            },
            {
                "@type": "BreadcrumbList",
                "@id": url_of(rel) + "#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
                    for i, (name, url) in enumerate(crumbs_for(rel))
                ],
            },
            {
                "@type": "WebPage",
                "@id": url_of(rel) + "#webpage",
                "url": url_of(rel),
                "name": title,
                "dateModified": date_mod,
                "isPartOf": {"@id": DOMAIN + "/#organization"},
                "breadcrumb": {"@id": url_of(rel) + "#breadcrumb"},
            },
        ],
    }
    return json.dumps(ld, separators=(",", ":"), ensure_ascii=False)


def strip_block(text):
    """Remove our own block plus any legacy favicon tags, so re-runs are stable."""
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), "", text, flags=re.S)
    text = re.sub(r'[ \t]*<link rel="icon"[^\n]*?>\n?', "", text)
    text = re.sub(r'[ \t]*<link rel="apple-touch-icon"[^\n]*?>\n?', "", text)
    while "\n\n</head>" in text:
        text = text.replace("\n\n</head>", "\n</head>")
    return text


def main(check=False):
    changed = 0
    missing = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for f in filenames:
            if not f.endswith(".html"):
                continue
            path = os.path.join(dirpath, f)
            rel = "/" + os.path.relpath(path, ROOT).replace("\\", "/")
            src = open(path, encoding="utf-8").read()
            m = re.search(r"<title>(.*?)</title>", src, re.S)
            title = m.group(1).strip() if m else ""
            if not title:
                missing.append(rel)
                continue
            date_mod = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).strftime("%Y-%m-%d")
            is_embed = rel.startswith("/embed/")
            robots = ("noindex,follow" if is_embed
                      else "index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1")
            block = (
                START
                + FAVICON
                + '<link rel="apple-touch-icon" href="/assets/img/thumbnail.png">'
                + f'<meta name="robots" content="{robots}">'
                + f'<meta property="og:url" content="{url_of(rel)}">'
                + '<meta property="og:site_name" content="ShutterMath">'
                + f'<meta name="twitter:title" content="{title}">'
                + f'<script type="application/ld+json">{graph(rel, title, date_mod)}</script>'
                + END
            )
            new = strip_block(src).replace("</head>", block + "\n</head>", 1)
            if new != src:
                changed += 1
                if not check:
                    open(path, "w", encoding="utf-8", newline="\n").write(new)
    print(f"{'would change' if check else 'changed'} {changed} files; no title: {missing}")


if __name__ == "__main__":
    main(check="--check" in sys.argv)

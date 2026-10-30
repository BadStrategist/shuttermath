"""Write a real, static header and footer into every page.

Why: main.js used to inject the nav at runtime. Crawlers and AI answer engines do
not run JavaScript, so no internal link existed for them, and the injected hrefs
were rewritten against a wrong base path, so readers on any subpage got 404s.
Idempotent: re-running replaces the same marker-delimited block.
"""
import os
import re
import sys

ROOT = r"C:\Users\tscac\Projects\_archive\shuttermath"
NAV = [
    ("Depth of Field", "/tools/depth-of-field.html"),
    ("Hyperfocal", "/tools/hyperfocal.html"),
    ("ND Filter", "/tools/nd-filter.html"),
    ("Flash GN", "/tools/flash-guide-number.html"),
    ("Pixel Scale", "/tools/pixel-scale.html"),
    ("Shutter Angle", "/tools/shutter-angle.html"),
    ("Crop Factor", "/tools/crop-factor.html"),
    ("Time Lapse", "/tools/time-lapse.html"),
    ("Stacking", "/tools/focus-stacking.html"),
    ("Blur", "/tools/background-blur.html"),
    ("Guides", "/pages/guides.html"),
]
FOOT = [
    ("Free Tools", "/pages/free-photography-calculators.html"),
    ("Field Kit", "/products.html"),
    ("About", "/pages/about.html"),
    ("Contact", "/pages/contact.html"),
    ("Privacy Policy", "/pages/privacy.html"),
    ("Terms", "/pages/terms.html"),
]

START_H = "<!-- CHROME:HEADER:START -->"
END_H = "<!-- CHROME:HEADER:END -->"
START_F = "<!-- CHROME:FOOTER:START -->"
END_F = "<!-- CHROME:FOOTER:END -->"


def header_html(current):
    links = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == current else ""
        links.append(f'<a href="{href}"{cur}>{label}</a>')
    return (
        START_H
        + '<div class="container">'
        '<a class="brand" href="/">Shutter<span>Math</span></a>'
        '<nav class="nav" aria-label="Main navigation">'
        + "".join(links)
        + '</nav><button class="nav-toggle" aria-label="Menu" aria-expanded="false">&#9776;</button></div>'
        + END_H
    )


def footer_html():
    links = "".join(f'<a href="{h}">{t}</a>' for t, h in FOOT)
    return (
        START_F
        + '<div class="container"><div><strong style="color:#fff">ShutterMath</strong><br>'
        "Photography calculators that know the camera you own</div>"
        f'<nav class="fnav" aria-label="Footer navigation">{links}</nav></div>'
        + END_F
    )


def main(check=False):
    changed = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for f in filenames:
            if not f.endswith(".html"):
                continue
            path = os.path.join(dirpath, f)
            rel = "/" + os.path.relpath(path, ROOT).replace("\\", "/")
            src = open(path, encoding="utf-8").read()
            orig = src
            cur = "" if rel in ("/index.html", "/") else rel
            if '<header class="site-header">' in src:
                src = re.sub(r'<header class="site-header">.*?</header>',
                             '<header class="site-header">' + header_html(cur) + "</header>",
                             src, count=1, flags=re.S)
            elif not rel.startswith("/embed/"):
                src = src.replace("<body>", '<body>\n<header class="site-header">' + header_html(cur) + "</header>", 1)
            if '<footer class="site-footer">' in src:
                src = re.sub(r'<footer class="site-footer">.*?</footer>',
                             '<footer class="site-footer">' + footer_html() + "</footer>",
                             src, count=1, flags=re.S)
            elif not rel.startswith("/embed/"):
                src = src.replace("</body>", '<footer class="site-footer">' + footer_html() + "</footer>\n</body>", 1)
            if src != orig:
                changed += 1
                if not check:
                    open(path, "w", encoding="utf-8", newline="\n").write(src)
    print(f"{'would change' if check else 'changed'} {changed} files")


if __name__ == "__main__":
    main(check="--check" in sys.argv)

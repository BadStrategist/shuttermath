"""Regenerate sitemap.xml from the files on disk, excluding embeddable widgets and 404.

lastmod comes from the file's own mtime, so a page that changed today reports today
instead of a September date that tells Google nothing changed.
"""
import os
from datetime import datetime, timezone

ROOT = r"C:\Users\tscac\Projects\_archive\shuttermath"
DOMAIN = "https://shuttermath.com"
SKIP_DIRS = {".git", "node_modules", "__pycache__", "embed", "scripts"}
SKIP_FILES = {"404.html"}


def main():
    urls = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in sorted(filenames):
            if not f.endswith(".html") or f in SKIP_FILES:
                continue
            path = os.path.join(dirpath, f)
            rel = "/" + os.path.relpath(path, ROOT).replace("\\", "/")
            if rel == "/index.html":
                loc = DOMAIN + "/"
            else:
                loc = DOMAIN + rel
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            urls.append((loc, mtime.strftime("%Y-%m-%d")))
    urls.sort()
    body = "\n".join(f"  <url><loc>{u}</loc><lastmod>{d}</lastmod></url>" for u, d in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{body}\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write(xml)
    print(f"sitemap: {len(urls)} urls")


if __name__ == "__main__":
    main()

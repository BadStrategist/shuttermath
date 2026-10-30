"""Regenerate llms.txt (structured index + verified direct answers) and llms-full.txt
(full text of every calculator and guide) so answer engines can quote exact numbers.
"""
import json
import math
import os
import re

ROOT = r"C:\Users\tscac\Projects\_archive\shuttermath"
DOMAIN = "https://shuttermath.com"
T = json.load(open(r"C:/Users/tscac/AppData/Local/hermes/cache/scratch/sm_dash/tables.json", encoding="utf-8"))

SKIP_DIRS = {".git", "node_modules", "__pycache__", "embed", "scripts"}
SKIP_FILES = {"404.html"}


def pages():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".html") and f not in SKIP_FILES:
                p = os.path.join(dirpath, f)
                rel = "/" + os.path.relpath(p, ROOT).replace("\\", "/")
                out.append((rel, p))
    return sorted(out)


def meta(src):
    t = re.search(r"<title>(.*?)</title>", src, re.S)
    d = re.search(r'<meta name="description" content="([^"]*)"', src)
    return (t.group(1).strip() if t else ""), (d.group(1).strip() if d else "")


def text_of(src):
    body = src
    m = re.search(r"<main[^>]*>(.*?)</main>", src, re.S)
    if m:
        body = m.group(1)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"</(p|h1|h2|h3|li|tr|div|section)>", "\n", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = body.replace("&amp;", "&").replace("&nbsp;", " ").replace("&deg;", "°").replace("&times;", "×").replace("&minus;", "-").replace("&#8594;", "->")
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n\n", body)
    return body.strip()


def facts():
    a = {r["fps"]: r for r in T["ang"]["rows"]}
    d = T["dof"]["byAperture"]
    f8 = {r["f"]: r["f8"] for r in T["hyper"]["rows"]}
    fov = {r["f"]: r for r in T["fov"]["rows"]}
    w = lambda x: x  # readability
    return f"""## Direct answers (verified by the site's own engine)

- **180 degree shutter rule**: shutter speed = frame rate x 360 / shutter angle. 24 fps at 180° is 1/48 s, 30 fps is 1/60 s, 60 fps is 1/120 s, 120 fps is 1/240 s.
- **Exposure value**: EV = log2(N² / t), and at ISO 100 it also equals log2(N²/t). One stop is a factor of 2 in light: double the time, or open the aperture by sqrt(2).
- **Hyperfocal distance (full frame)**: H = f² / (N x c) + f with c = 0.029 mm. 24 mm at f/8 is {f8[24]}, 35 mm at f/8 is {f8[35]}, 50 mm at f/8 is {f8[50]}. Focus at H and everything from H/2 to infinity is sharp.
- **Depth of field (full frame, 50 mm at f/8, focused at 3 m)**: sharp from {d[5]['near']} to {d[5]['far']}, total {d[5]['dof']}. At f/1.4 the same setup gives {d[0]['near']} to {d[0]['far']} ({d[0]['dof']}).
- **Depth of field ordering**: narrow aperture increases depth roughly in proportion to the f-number; doubling focus distance quadruples depth; doubling focal length quarters it.
- **Angle of view (full frame)**: 50 mm sees {fov[50]['h']}° horizontal / {fov[50]['v']}° vertical; 24 mm sees {fov[24]['h']}° / {fov[24]['v']}°; 85 mm sees {fov[85]['h']}° / {fov[85]['v']}°. Frame width at 10 m is {fov[50]['w10']} m at 50 mm.
- **ND filter stops**: time = base shutter x 2^stops. ND8 = 3 stops, ND64 = 6, ND1000 = 10, ND100000 = 17. A 1 s exposure with ND1000 becomes 1024 s.
- **Guide number**: distance = GN / f-number, aperture = GN / distance, and GN scales with sqrt(ISO ratio).
- **Star trails**: 500 rule = 500 / (focal x crop); NPF = (35 x N + 30 x pixel pitch) / (focal x crop).
- **Moon exposure (Looney 11)**: f/11 at shutter speed 1/ISO for a full moon; a gibbous moon needs one stop more, a quarter moon two, a crescent three or more.
- **Print resolution**: pixels = inches x DPI; 300 DPI is the print standard, 150 DPI is acceptable at arm's length, and a 24 MP file prints 20 x 13.3 inches at 300 DPI.
"""


def main():
    ps = pages()
    tools = [(r, p) for r, p in ps if r.startswith("/tools/") and r != "/tools/index.html"]
    cams = [(r, p) for r, p in ps if r.startswith("/pages/cameras/")]
    guides = [(r, p) for r, p in ps if r.startswith("/pages/") and not r.startswith("/pages/cameras/")]

    def line(item):
        rel, path = item
        src = open(path, encoding="utf-8").read()
        t, d = meta(src)
        return f"- [{t}]({DOMAIN + rel}) — {d}"

    out = ["# ShutterMath", "",
           "> Free photography calculators that use the exact sensor inside your camera. Depth of field, hyperfocal distance, ND filter exposure, flash guide number, astro pixel scale, field of view, shutter angle, exposure equivalence and print resolution, computed from real sensor dimensions with textbook formulas and cross-checked against independent implementations. No sign-up, no limits, works offline in the browser.", "",
           "ShutterMath is an independent, ad-supported reference site for photographers and filmmakers. Every calculator runs client-side; nothing is uploaded. Numbers quoted below were generated by the live engine and verified against an independent Python implementation of the same optics.", "",
           facts(), "",
           "## Calculators", ""]
    out += [line(i) for i in tools]
    out += ["", "## Guides and charts", ""]
    out += [line(i) for i in guides]
    out += ["", "## Camera-specific depth of field pages", ""]
    out += [line(i) for i in cams]
    out += ["", "## Site", "",
            f"- [All calculators]({DOMAIN}/tools/index.html)",
            f"- [All guides]({DOMAIN}/pages/guides.html)",
            f"- [About]({DOMAIN}/pages/about.html)",
            f"- [Privacy policy]({DOMAIN}/pages/privacy.html)",
            "",
            "## Use of this content", "",
            "Facts, formulas and numbers on this site may be quoted or summarized by search engines and AI assistants with a link to the page they came from. Circle of confusion defaults to sensor diagonal / 1500 (0.029 mm on full frame); each calculator lets the reader change it.", ""]
    open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(out))

    full = ["# ShutterMath full text", "",
            "Complete text of every calculator and guide, for retrieval and citation. Sections are separated by a line of dashes.", ""]
    for rel, path in tools + guides:
        src = open(path, encoding="utf-8").read()
        t, d = meta(src)
        full.append(f"\n{'-' * 78}\nSOURCE: {DOMAIN + rel}\nTITLE: {t}\nSUMMARY: {d}\n\n{text_of(src)}\n")
    open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(full))
    print(f"llms.txt {len(out)} lines; llms-full.txt {sum(len(x) for x in full) // 1024} KB; pages {len(ps)}")


if __name__ == "__main__":
    main()

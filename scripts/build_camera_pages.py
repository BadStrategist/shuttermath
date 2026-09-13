#!/usr/bin/env python3
"""Deepen the highest-ranking camera pages with body-specific, computed data.

The 48 per-camera pages share one template (identical intro sentence, identical
"How to use this page" paragraph, identical FAQ set). That sameness is what a
scaled-content update punishes, and these pages are the site's best performers
(positions 2-15), so they are worth real differentiation rather than more volume.

This script touches a CURATED list only (CURATED, below) and is idempotent: the
generated content lives between <!-- CAMP:START --> / <!-- CAMP:END --> markers,
and the body-specific prose replaces the boilerplate by pattern match.

Every number comes from data/cameras.json and is recomputed here, so a spec fix in
the DB propagates. Idempotent + verifiable: re-run after any DB change.

  python scripts/build_camera_pages.py [--check]

--check prints what would change without writing.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cameras.json"
CAMDIR = ROOT / "pages" / "cameras"
LAMBDA_UM = 0.55          # µm, photopic peak used for the diffraction limit
FF_AREA = 36.0 * 24.0
FF_DIAG = math.hypot(36.0, 24.0)
START, END = "<!-- CAMP:START -->", "<!-- CAMP:END -->"

# Bodies worth investing in = the ones GSC shows ranking (position <= ~15 in the
# Aug 5-31 or Sep 1-10 windows, See scripts/serp_tracker.py + the 2026-09-12 audit).
CURATED = [
    "Samsung Galaxy S25 Ultra", "iPhone 15 Pro Max",
    "Sony ZV-E10", "Sony A6000", "Sony A6700",
    "Canon EOS R50", "Canon EOS R100",
    "Sony FX3", "Canon EOS R5 II", "Canon EOS R6", "Canon EOS R8",
    "Panasonic Lumix S5 II", "Leica Q3", "Nikon Z9",
    "OM System OM-1 II", "Panasonic Lumix GH7",
]

FORMAT_NOTE = {
    "Full Frame": ("A 36×24 mm chip is the reference size every other format is measured "
                   "against, so its depth of field is the shallowest per framing and its "
                   "sensors tolerate the smallest apertures before diffraction shows."),
    "APS-C": ("This is a crop sensor: the same lens frames tighter, so depth of field is "
              "deeper at matched framing — good for reach and handholdable landscapes, "
              "less so for the thinnest possible background melt."),
    "Micro 4/3": ("A 2× crop gives the deepest depth of field per framing of any "
                  "interchangeable-lens format here, which is why it is popular for macro "
                  "and handheld landscape — the sharp zone starts sooner."),
    "Phone": ("A phone sensor is tiny, so depth of field at matched framing is enormous — "
              "real background blur comes from computational processing, not optics."),
}


def load_bodies():
    data = json.loads(DB.read_text(encoding="utf-8"))
    return data["cameras"]


def specs(c):
    w, h, pw, ph = c["sensor_w"], c["sensor_h"], c["px_w"], c["px_h"]
    diag = math.hypot(w, h)
    pitch = (w * 1000.0) / pw
    mp = pw * ph / 1e6
    # Phone sensors are read out binned in normal use: 48/50 MP bodies bin 2×2,
    # 200 MP bodies bin 4×4 to a ~12 MP file. The native pitch is a best case.
    binning = (4 if mp >= 100 else 2) if c["format"] == "Phone" else 1
    return {
        "w": w, "h": h, "pw": pw, "ph": ph,
        "diag": diag,
        "coc": diag / 1500.0,
        "crop": FF_DIAG / diag,
        "mp": mp,
        "pitch": pitch,
        "area": w * h,
        "area_pct": (w * h) / FF_AREA * 100.0,
        "dla": pitch / (1.22 * LAMBDA_UM),
        "binning": binning,
        "binned_pitch": pitch * binning,
        "binned_mp": mp / (binning ** 2),
        "binned_dla": (pitch * binning) / (1.22 * LAMBDA_UM),
        "print_long": max(pw, ph) / 300.0,
        "print_short": min(pw, ph) / 300.0,
    }


def hfov_deg(width_mm, focal_mm):
    return math.degrees(2.0 * math.atan(width_mm / (2.0 * focal_mm)))


def fmt_num(v, dp=1):
    return f"{v:,.{dp}f}"


def body_block(c, db):
    s = specs(c)
    name, fmt = c["name"], c["format"]
    dl = db.get(name)
    # closest same-format siblings by sensor area
    sib = sorted((x for x in db.values() if x["format"] == fmt and x["name"] != name),
                 key=lambda x: abs(x["sensor_w"] * x["sensor_h"] - s["area"]))[:3]

    rows = [
        ("Sensor size", f'{s["w"]:.1f} × {s["h"]:.1f} mm',
         f'{fmt} — {s["area_pct"]:.0f}% of a full-frame sensor\'s area'),
        ("Crop factor", f'{s["crop"]:.2f}×',
         f'a {fmt} sensor records {s["crop"]:.2f}× the focal length, so a 50 mm lens frames like '
         f'{50 * s["crop"]:.0f} mm on full frame'),
        ("Native resolution", f'{s["mp"]:.0f} MP ({s["pw"]} × {s["ph"]})',
         f'prints {s["print_long"]:.1f} × {s["print_short"]:.1f} in at 300 ppi'
         + (' from the full-resolution file — lens and noise, not pixel count, cap a real print'
            if fmt == "Phone" else '')),
        ("Pixel pitch", f'{s["pitch"]:.2f} µm',
         'how much sensor area each pixel gets — the smaller the pitch, the sooner diffraction bites'),
        ("Circle of confusion", f'{s["coc"]:.4f} mm',
         'the sharpness yardstick this page\'s depth-of-field numbers are built on (sensor diagonal ÷ 1500)'),
        ("Diffraction limit", f'≈ f/{s["dla"]:.1f}'
         + (f' native / ≈ f/{s["binned_dla"]:.1f} binned' if fmt == "Phone" else ''),
         'past this aperture the airy disc outgrows a pixel pair and resolution falls, even though depth of field keeps growing'),
    ]
    tr = "\n".join(
        f'      <tr><td>{k}</td><td class="num">{v}</td><td>{note}</td></tr>' for k, v, note in rows)

    focal_rows = [
        f'      <tr><td class="num">{f} mm</td><td class="num">{hfov_deg(s["w"], f):.1f}°</td>'
        f'<td class="num">{f * s["crop"]:.0f} mm</td>'
        f'<td class="num">{hfov_deg(36.0, f):.1f}°</td></tr>'
        for f in (16, 24, 35, 50, 85)]

    sib_rows = []
    for x in sib:
        xs = specs(x)
        slug = slugify(x["name"])
        sib_rows.append(
            f'      <tr><td><a href="{slug}.html">{x["name"]}</a></td>'
            f'<td class="num">{xs["area"]:.0f} mm²</td><td class="num">{xs["mp"]:.0f} MP</td>'
            f'<td class="num">{xs["pitch"]:.2f} µm</td><td class="num">≈ f/{xs["dla"]:.1f}</td></tr>')

    phone_note = ""
    if fmt == "Phone":
        phone_note = (
            f'\n  <div class="callout warn">📱 <strong>About that megapixel count:</strong> the '
            f'{name} lists its {s["mp"]:.0f} MP mode, which is a special full-resolution capture. '
            f'Normal shots come out binned to roughly {s["binned_mp"]:.0f} MP, which multiplies the '
            f'effective pixel pitch to about {s["binned_pitch"]:.2f} µm and moves the diffraction '
            f'limit out to roughly f/{s["binned_dla"]:.1f} — so the {s["pitch"]:.2f} µm figure is a '
            f'best case, not what everyday frames are made of. Phone lenses sit near f/1.7–f/2.4 and '
            f'rarely stop down at all, so diffraction is not what limits a phone photo — the lens and '
            f'the sensor\'s size are.</div>')

    return f'''{START}
  <p class="muted mt1">{name} key specs: {s["mp"]:.0f} MP · {s["crop"]:.2f}× crop factor · {s["pitch"]:.2f} µm pixels · CoC {s["coc"]:.4f} mm (standard diagonal ÷ 1500). The depth-of-field values below assume focus at 5 m.</p>

  <h2>Sensor profile: what the {name} sensor means for depth of field</h2>
  <p>{FORMAT_NOTE[fmt]}</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Property</th><th>Value</th><th>What it changes</th></tr></thead>
    <tbody>
{tr}
    </tbody>
  </table></div>
{phone_note}
  <h2>Framing on the {name}: focal length vs angle of view</h2>
  <p>Because this is a {s["crop"]:.2f}× sensor, focal lengths land differently than on full frame. Horizontal angle of view below is computed from the sensor's exact {s["w"]:.1f} mm width.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Focal length</th><th>Horizontal angle of view</th><th>35 mm equivalent</th><th>Full-frame angle for that equivalent</th></tr></thead>
    <tbody>
{chr(10).join(focal_rows)}
    </tbody>
  </table></div>

  <h2>How the {name} compares to other {fmt} bodies</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Body</th><th>Sensor area</th><th>Resolution</th><th>Pixel pitch</th><th>Diffraction limit</th></tr></thead>
    <tbody>
      <tr><td><strong>{name}</strong></td><td class="num">{s["area"]:.0f} mm²</td><td class="num">{s["mp"]:.0f} MP</td><td class="num">{s["pitch"]:.2f} µm</td><td class="num">≈ f/{s["dla"]:.1f}</td></tr>
{chr(10).join(sib_rows)}
    </tbody>
  </table></div>
  <p class="muted">All values computed from the same sensor database the calculators use. Datasheet dimensions vary by a tenth of a millimetre between sources; the relative ordering here is what matters.</p>
{END}'''


def slugify(name):
    return name.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(".", "")


def body_prose(c, db):
    """Body-specific replacements for the two boilerplate paragraphs."""
    s = specs(c)
    name, fmt = c["name"], c["format"]
    if fmt == "Full Frame":
        framing = (f'It is a full-frame sensor, so depth of field depends only on focal length, '
                   f'aperture and focus distance — no crop conversion needed, and f/8 still behaves '
                   f'like f/8.')
    else:
        framing = (f'Matching the field of view of a 50 mm lens on full frame takes only '
                   f'{50 / s["crop"]:.0f} mm here, and at that matched framing an f/2.8 lens gives the '
                   f'same depth of field as f/{2.8 * s["crop"]:.1f} on full frame.')
    intro = (f'{name} depth of field, computed from its exact {s["w"]:.1f}×{s["h"]:.1f} mm sensor, '
             f'{s["mp"]:.0f} MP resolution and {s["coc"]:.4f} mm circle of confusion — the numbers its '
             f'own calculators use, not a generic preset. {framing}')
    howto = (
        f'Find your lens and aperture, read the near–far range, and compose inside it — or open the '
        f'interactive calculator to drag the focus distance live. On the {name} the practical ceiling '
        f'is about f/{s["binned_dla"] if fmt == "Phone" else s["dla"]:.1f}: stopping down past that '
        f'deepens the sharp zone but starts costing detail to diffraction, so lean on the hyperfocal '
        f'column instead of the smallest aperture on the dial. For the formula and the '
        f'circle-of-confusion convention behind these numbers, see the '
        f'<a href="../circle-of-confusion.html">circle of confusion guide</a>.')
    faq_q = f'What is the diffraction limit of the {name}?'
    faq_a = (f'About f/{s["binned_dla"] if fmt == "Phone" else s["dla"]:.1f}. At a '
             f'{s["binned_pitch"] if fmt == "Phone" else s["pitch"]:.2f} µm effective pixel pitch there '
             f'comes a point where the airy disc from an ever-smaller aperture covers more than a pixel '
             f'can resolve, so sharpness stops improving. That is the number to stop at, not f/16 or f/22.')
    return intro, howto, faq_q, faq_a


def patch_page(path: Path, c, db, check=False):
    html = path.read_text(encoding="utf-8")
    before = html
    name = c["name"]
    intro, howto, faq_q, faq_a = body_prose(c, db)
    notes = []

    # 1. the generated data block (insert once, at the key-specs paragraph)
    block = body_block(c, db)
    if START in html:
        html = re.sub(re.escape(START) + r".*?" + re.escape(END), block, html, flags=re.S)
        notes.append("block refreshed")
    else:
        m = re.search(r'  <p class="muted mt1">.*?key specs:.*?</p>\n', html, flags=re.S)
        if not m:
            raise SystemExit(f"! {path.name}: no key-specs anchor to insert at")
        html = html[:m.start()] + block + "\n" + html[m.end():]
        notes.append("block inserted")

    # 2. the boilerplate intro sentence -> body-specific
    new_intro = f'  <p class="muted">{intro}</p>'
    html2 = re.sub(r'  <p class="muted">Depth of field is the range of distances.*?</p>', new_intro, html, count=1, flags=re.S)
    if html2 != html:
        notes.append("intro replaced")
    html = html2

    # 3. the boilerplate "How to use this page" paragraph -> body-specific
    html2 = re.sub(r'<p>Find your lens and aperture.*?</p>', f'<p>{howto}</p>', html, count=1, flags=re.S)
    if html2 != html:
        notes.append("how-to replaced")
    html = html2

    # 4. one extra FAQ, in the visible list AND the FAQPage JSON-LD (kept in sync)
    if faq_q not in html:
        head, sep, tail = html.partition('<div class="faq">')
        if sep and faq_q not in head:          # visible FAQ list
            item = f'\n    <details><summary>{faq_q}</summary><p>{faq_a}</p></details>'
            html = head + sep + item + tail
            notes.append("faq added")
        # mirror into the FAQPage JSON-LD array
        if '"@type":"FAQPage"' in html:
            q_json = json.dumps({"@type": "Question", "name": faq_q,
                                 "acceptedAnswer": {"@type": "Answer", "text": faq_a}},
                                separators=(",", ":"))
            html2 = html.replace("}\n]}\n</script>", "},\n" + q_json + "\n]}\n</script>", 1)
            if html2 != html:
                notes.append("faq schema synced")
            html = html2

    # 5. og:description should match the new page, not the old boilerplate
    html = re.sub(r'(<meta property="og:description" content=")[^"]*(">)',
                  lambda m: m.group(1) + intro.replace('"', "&quot;") + m.group(2), html, count=1)

    # 6. lastmod freshness is handled by the sitemap updater
    if html == before:
        return None, ["no change"]
    if not check:
        path.write_text(html, encoding="utf-8")
    return html, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    db = {c["name"]: c for c in load_bodies()}
    missing = [n for n in CURATED if n not in db]
    if missing:
        raise SystemExit(f"! not in data/cameras.json: {missing}")

    changed = 0
    for name in CURATED:
        c = db[name]
        path = CAMDIR / f"{slugify(name)}.html"
        if not path.exists():
            print(f"{path.name:<34} MISSING FILE")
            continue
        _, notes = patch_page(path, c, db, check=args.check)
        if notes != ["no change"]:
            changed += 1
        print(f"{path.name:<34} {', '.join(notes)}")
    print(f"\n{len(CURATED)} pages {'checked' if args.check else 'processed'}, {changed} changed")


if __name__ == "__main__":
    main()

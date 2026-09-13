#!/usr/bin/env python3
"""Build the field-of-view reference table on tools/field-of-view.html.

Replaces the block between <!-- FOV-REFTABLE:START --> and <!-- FOV-REFTABLE:END -->,
inserting it before the "Related tools" heading on first run. Math is computed here
(not typed) so the table can never drift from the calculator's formula:

    horizontal AoV = 2 * atan(sensor_width  / (2 * focal_length))
    vertical   AoV = 2 * atan(sensor_height / (2 * focal_length))

Run:  python scripts/build_fov_reference.py
"""
from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "tools" / "field-of-view.html"
START, END = "<!-- FOV-REFTABLE:START -->", "<!-- FOV-REFTABLE:END -->"

SENSORS = [
    ("Full frame", "36 × 24 mm", 36.0, 24.0),
    ("APS-C (1.5×)", "23.5 × 15.6 mm", 23.5, 15.6),
    ("APS-C Canon (1.6×)", "22.3 × 14.9 mm", 22.3, 14.9),
    ("Micro 4/3", "17.3 × 13 mm", 17.3, 13.0),
    ("1-inch", "13.2 × 8.8 mm", 13.2, 8.8),
]
FOCALS = [14, 16, 20, 24, 28, 35, 50, 85, 100, 135, 200, 300, 400]


def aov(dim: float, focal: float) -> float:
    return 2.0 * math.degrees(math.atan(dim / (2.0 * focal)))


def build() -> str:
    heads = "".join(
        f'<th class="num">{name}<br><span style="font-weight:400;text-transform:none">{dims}</span></th>'
        for name, dims, _w, _h in SENSORS
    )
    rows = []
    for f in FOCALS:
        cells = "".join(f'<td class="num">{aov(w, f):.1f}°</td>' for _n, _d, w, _h in SENSORS)
        rows.append(f'<tr><td><strong>{f} mm</strong></td>{cells}</tr>')
    return f"""{START}
  <h2>Field of view reference table (focal length × sensor)</h2>
  <p>Horizontal angle of view in degrees for each focal length and sensor format. Divide-by-two, roughly: a 24 mm lens on full frame sees about 74°, and the same lens on APS-C sees about 52° — which is why a 24 mm on a crop body frames like a 36 mm on full frame.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Focal length</th>{heads}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
  <p class="muted">Values are horizontal angles of view computed as 2·atan(sensor width ÷ (2 × focal length)), rounded to 0.1°. Vertical and diagonal angles, and the 35 mm equivalent for your exact body, are in the <a href="#fov-tool">calculator above</a>.</p>
  <div class="callout mt1">📐 <strong>Rule of thumb:</strong> doubling the focal length halves the angle of view. 24 mm → 74°, 48 mm → 37°, 96 mm → 18°. Equally, moving a lens from full frame to Micro 4/3 (2.0× crop) halves it again.</div>
{END}"""


def main() -> int:
    html = PAGE.read_text(encoding="utf-8")
    block = build()
    if START in html and END in html:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _m: block, html, flags=re.S)
        action = "replaced"
    else:
        anchor = re.search(r'\n\s*<h2>Related tools', html)
        if not anchor:
            print("FAIL: no anchor heading to insert before")
            return 1
        new = html[:anchor.start()] + "\n" + block + html[anchor.start():]
        action = "inserted"
    PAGE.write_text(new, encoding="utf-8")
    print(f"{action} FOV reference table ({len(FOCALS)} focal lengths × {len(SENSORS)} sensors) -> {PAGE.relative_to(ROOT)}")
    print("sanity: 24mm FF =", round(aov(36.0, 24), 1), "| 50mm FF =", round(aov(36.0, 50), 1),
          "| 50mm APS-C 1.5x =", round(aov(23.5, 50), 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

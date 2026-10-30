"""Retune titles and meta descriptions on pages that already earn impressions but
almost no clicks (Search Console, Sep 28 - Oct 27 2026). Keyword first, then a
concrete number the snippet can show. Prints length checks.
"""
import re

ROOT = r"C:\Users\tscac\Projects\_archive\shuttermath"

NEW = {
    "tools/depth-of-field.html": (
        "Depth of Field Calculator: Exact Near and Far Limits",
        "Enter focal length, aperture and focus distance for the exact near limit, far limit and total depth of field, using your camera's real circle of confusion.",
    ),
    "tools/shutter-angle.html": (
        "Shutter Angle Calculator: 180\u00b0 Rule Speed by Frame Rate",
        "24 fps at 180\u00b0 is 1/48 s and 60 fps at 180\u00b0 is 1/120 s. Enter frame rate and shutter angle for the exact speed, plus the full 180\u00b0 reference table.",
    ),
    "tools/moon-exposure.html": (
        "Moon Exposure Calculator: Shutter Speed by Lunar Phase",
        "Looney 11 is f/11 at 1/ISO. At ISO 100 a full moon needs 1/100 s; a thin crescent needs 8 stops more. Enter phase, ISO and aperture for the exact time.",
    ),
    "tools/field-of-view.html": (
        "Angle of View Calculator: Focal Length to Field of View",
        "A 50mm lens on full frame sees 39.6\u00b0 across and 27\u00b0 high. Enter focal length and sensor for the angle of view and the frame you fill at any distance.",
    ),
    "tools/video-nd.html": (
        "Video ND Calculator: Stops for the 180\u00b0 Shutter Rule",
        "Enter frame rate and shutter angle, then the shutter speed your meter gives. Get the exact ND stops and the nearest filter that keeps motion blur natural.",
    ),
    "tools/hyperfocal.html": (
        "Hyperfocal Distance Calculator: Focus Once, Sharp to Infinity",
        "24mm at f/8 on full frame is hyperfocal at 2.5 m, so everything from 1.25 m to infinity is sharp. Enter your focal length, aperture and sensor for the exact distance.",
    ),
}


def main():
    for rel, (title, desc) in NEW.items():
        path = ROOT + "\\" + rel.replace("/", "\\")
        src = open(path, encoding="utf-8").read()
        orig = src
        src = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", src, count=1, flags=re.S)
        src = re.sub(r'<meta name="description" content="[^"]*">',
                     f'<meta name="description" content="{desc}">', src, count=1)
        src = re.sub(r'<meta property="og:title" content="[^"]*">',
                     f'<meta property="og:title" content="{title}">', src, count=1)
        src = re.sub(r'<meta property="og:description" content="[^"]*">',
                     f'<meta property="og:description" content="{desc}">', src, count=1)
        if src != orig:
            open(path, "w", encoding="utf-8", newline="\n").write(src)
        print(f"{len(title):>3} | {len(desc):>3} | {rel}")


if __name__ == "__main__":
    main()

"""Shadow evaluation of TypeSafe Jev on real ShutterMath artifacts.

Two experiments, both against labels that already exist in this repo:

1. Differentiation gate. Commit 89b32c9 replaced 16 identical-template camera
   pages with body-specific copy. That gives 32 labelled documents: 16 templated
   (before) and 16 differentiated (after). We ask Jev whether each document is
   body-specific, then check whether its probability separates the two classes.

2. Query to page routing. data/serp_track.csv records the page this site targets
   for each tracked query. We ask Jev to pick the intended page out of all 79
   candidates, and compare against a plain lexical baseline.

Nothing here writes to the site. Results land in scripts/jev_shadow_results.json.
"""

import concurrent.futures as futures
import csv
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = "jev-1.13.0"
COMMIT = "89b32c9"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
CACHE_PATH = ROOT / "scripts" / "jev_shadow_results.json"
BODY_CHARS = 3500
WORKERS = 6


def api_key():
    envp = pathlib.Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"
    for line in envp.read_text(encoding="utf-8").splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("TYPESAFE_API_KEY not found in hermes/.env")


KEY = api_key()
CACHE = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
CACHE_LOCK = threading.Lock()


def save_cache():
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(CACHE, indent=1), encoding="utf-8")
    os.replace(tmp, CACHE_PATH)


def call(key, state, questions):
    if key in CACHE:
        return CACHE[key]
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.load(r)
            break
        except Exception as e:  # rate limit or transient
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        out = {"error": str(last)}
    CACHE[key] = out
    with CACHE_LOCK:
        save_cache()
    return out


def body_text(html):
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    frag = m.group(1) if m else html
    frag = re.sub(r"<(script|style|nav)\b.*?</\1>", " ", frag, flags=re.S | re.I)
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = re.sub(r"&[a-z]+;", " ", frag)
    return re.sub(r"\s+", " ", frag).strip()[:BODY_CHARS]


def git_old(path):
    out = subprocess.run(["git", "show", COMMIT + "^:" + path], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return out.stdout


def diff_questions():
    return {
        "body_specific": {
            "type": "noul",
            "instructions": {
                "question": "Is this page copy written for this specific camera body, or is it generic template text that would read the same for any camera?",
                "inspect": "`page.text`",
                "focus": "Look for measured values, this body's own sensor numbers, and names of this body or its close siblings.",
            },
            "criteria": {
                "true": {
                    "what": "The copy carries facts that are true of this body and not of cameras in general",
                    "examples": ["states this body's sensor size, pixel pitch or diffraction limit",
                                 "names this body or its same-format siblings in a comparison"],
                },
                "false": {
                    "what": "The copy is a shared template that would read correctly for any camera",
                    "not_for": "A page that happens to be short but still carries this body's own numbers",
                    "examples": ["identical intro and FAQ wording used across many bodies",
                                 "no numbers or names specific to this body"],
                },
            },
        },
        "specificity": {
            "type": "score",
            "instructions": {
                "question": "How specific is this copy to this one camera body?",
                "inspect": "`page.text`",
                "focus": "Judge specificity to the body, not writing quality.",
            },
            "criteria": [
                "generic text that fits any camera",
                "partly specific, some facts are shared boilerplate",
                "clearly written around this body's own measurements",
            ],
        },
    }


def eq_questions():
    """Single condition, no either/or framing. Label is code-verified: 0 of the 16
    templated pages state a full-frame equivalence, all 16 differentiated ones do."""
    return {
        "states_equivalence": {
            "type": "noul",
            "instructions": {
                "question": "Does this copy state what this camera's settings are equivalent to on a full frame camera, that is an equivalent focal length or an equivalent aperture?",
                "inspect": "`page.text`",
                "focus": "Look only for a stated equivalence to full frame. Generic mention of a crop factor is not enough; the copy must state what a setting on this body equals elsewhere.",
            },
            "criteria": {
                "true": {
                    "what": "The copy states a full frame equivalence with a value",
                    "examples": ["says a 50 mm lens on full frame is matched by 31 mm here",
                                 "says f/2.8 here gives the same depth of field as f/4.5 on full frame"],
                },
                "false": {
                    "what": "The copy does not state any full frame equivalence",
                    "not_for": "Copy that lists a crop factor but never says what any setting equals on full frame",
                    "examples": ["only lists sensor size, resolution and a depth of field table"],
                },
            },
        },
    }


def run_diff(questions=None, prefix="diff"):
    files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", COMMIT],
        capture_output=True, text=True, cwd=ROOT).stdout.split()
    files = [f for f in files if f.startswith("pages/cameras/") and f.endswith(".html")]
    rows = []
    for f in files:
        name = pathlib.Path(f).stem
        rows.append((name, "before", git_old(f)))
        rows.append((name, "after", (ROOT / f).read_text(encoding="utf-8", errors="replace")))
    qs = questions or diff_questions()

    def work(item):
        name, label, html = item
        txt = body_text(html)
        res = call(prefix + ":" + name + ":" + label, {"page": {"text": txt}}, qs)
        return name, label, len(txt), res

    with futures.ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(work, rows))
    return results


def candidate_pages():
    """Every real page on the site. Coverage matters: a page that is not on the
    ballot can never be chosen, which silently turns the model's answers into
    noise."""
    pages = []
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("embed/", ".git/")) or rel in ("404.html",):
            continue
        html = p.read_text(encoding="utf-8", errors="replace")
        t = re.search(r"<title>(.*?)</title>", html, re.S)
        d = re.search(r'name="description"\s+content="(.*?)"', html, re.S)
        pages.append({
            "path": "/" + rel,
            "title": (t.group(1).strip() if t else p.stem).split("|")[0].strip(),
            "desc": re.sub(r"\s+", " ", d.group(1)).strip() if d else "",
        })
    return pages


def run_routing(hinted=False):
    pages = candidate_pages()
    criteria = {p["path"]: (p["title"] + " :: " + p["desc"]) for p in pages}
    rows = list(csv.DictReader((ROOT / "data" / "serp_track.csv").open(encoding="utf-8")))
    out = []
    for row in rows:
        q = row["query"].strip()
        target = row["target_page"].strip()
        if not q or not target:
            continue
        instructions = {
            "question": "Which page of this site is the intended landing page for this search query?",
            "inspect": "`query` and `site_pages`",
            "focus": "Match the query's topic to the page that owns that topic.",
        }
        if hinted:
            instructions["site_conventions"] = (
                "This site has two kinds of page. Paths under /tools/ are interactive calculators. "
                "Paths under /pages/ are reference or explainer articles. The site's own target for a "
                "query that names a calculator or a chart is the matching calculator or chart page, not "
                "the topic overview and not an index page."
            )
        res = call(("route4:" if not hinted else "route4h:") + q, {"query": q, "site_pages": pages}, {
            "intended_page": {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            },
        })
        coverage = target in criteria
        # lexical baseline: share of query words found in the candidate path or title
        qw = set(re.findall(r"[a-z]+", q.lower()))
        scored = []
        for p in pages:
            hay = set(re.findall(r"[a-z]+", (p["path"] + " " + p["title"]).lower()))
            scored.append((len(qw & hay) / max(1, len(qw)), p["path"]))
        scored.sort(reverse=True)
        out.append({
            "query": q, "target": target, "served": row.get("served_page", "").strip(),
            "impressions": row.get("impressions", ""), "position": row.get("position", ""),
            "target_on_ballot": coverage, "candidates": len(pages),
            "baseline_top1": scored[0][1],
            "baseline_top3": [s[1] for s in scored[:3]],
            "jev": res,
        })
    return out


def summarize_diff(results):
    probs = {"before": [], "after": []}
    scores = {"before": [], "after": []}
    first_noul = None
    for name, label, n, res in results:
        a = (res.get("answers") or {})
        for k, v in a.items():
            if "noul" in v:
                first_noul = first_noul or k
                if k == first_noul:
                    probs[label].append(v["noul"])
            elif "score" in v:
                scores[label].append(v["score"])
    print("\n=== 1. differentiation gate (16 templated vs 16 differentiated) ===")
    print("question:", first_noul)
    if not probs["before"]:
        print("no answers:", json.dumps(results[0][3])[:300] if results else "no results")
        return
    print("noul, templated (want low): mean %.3f  min %.3f  max %.3f" %
          (sum(probs["before"]) / len(probs["before"]), min(probs["before"]), max(probs["before"])))
    print("noul, differentiated (want high): mean %.3f  min %.3f  max %.3f" %
          (sum(probs["after"]) / len(probs["after"]), min(probs["after"]), max(probs["after"])))
    print("score, templated: mean %.2f | differentiated: mean %.2f" %
          (sum(scores["before"]) / max(1, len(scores["before"])),
           sum(scores["after"]) / max(1, len(scores["after"]))))
    correct = sum(1 for p in probs["before"] if p < 0.5) + sum(1 for p in probs["after"] if p >= 0.5)
    print("accuracy at 0.5: %d/%d = %.1f%%" % (correct, len(probs["before"]) + len(probs["after"]),
                                               100 * correct / (len(probs["before"]) + len(probs["after"]))))
    best = (0, 0)
    for i in range(1, 100):
        t = i / 100
        c = sum(1 for p in probs["before"] if p < t) + sum(1 for p in probs["after"] if p >= t)
        if c > best[1]:
            best = (t, c)
    print("best threshold %.2f -> %.1f%% (overfit on 32 items, treat as an upper bound)" %
          (best[0], 100 * best[1] / (len(probs["before"]) + len(probs["after"]))))
    print("items where the gate would be uncertain (0.3 to 0.7):",
          sum(1 for p in probs["before"] + probs["after"] if 0.3 < p < 0.7))
    print("\nper item (name, label, probability):")
    for name, label, n, res in sorted(results):
        a = res.get("answers") or {}
        v = None
        for k, val in a.items():
            if "noul" in val:
                v = val["noul"]
                break
        print("  %-22s %-6s %s" % (name, label, "%.3f" % v if v is not None else "n/a"))


def summarize_routing(rows):
    print("\n=== 2. query to page routing (%d tracked queries) ===" % len(rows))
    if not rows:
        print("no rows")
        return
    off = [r for r in rows if not r.get("target_on_ballot")]
    print("candidates on ballot: %d | queries whose target was NOT on the ballot: %d" %
          (rows[0].get("candidates", 0), len(off)))
    rows = [r for r in rows if r.get("target_on_ballot")]
    jav1 = jav3 = base1 = base3 = 0
    for r in rows:
        a = (r["jev"].get("answers") or {}).get("intended_page") or {}
        pick = a.get("choice")
        probs = a.get("probabilities") or {}
        top3 = [k for k, _ in sorted(probs.items(), key=lambda kv: -kv[1])[:3]]
        jav1 += pick == r["target"]
        jav3 += r["target"] in top3
        base1 += r["baseline_top1"] == r["target"]
        base3 += r["target"] in r["baseline_top3"]
        print("  %-32s target=%-42s jev=%-42s conf=%s" %
              (r["query"][:32], r["target"], str(pick), a.get("confidence")))
    n = len(rows)
    print("top-1: jev %d/%d (%.0f%%) | lexical baseline %d/%d (%.0f%%)" %
          (jav1, n, 100 * jav1 / n, base1, n, 100 * base1 / n))
    print("top-3: jev %d/%d (%.0f%%) | lexical baseline %d/%d (%.0f%%)" %
          (jav3, n, 100 * jav3 / n, base3, n, 100 * base3 / n))


def load_cameras():
    data = json.loads((ROOT / "data" / "cameras.json").read_text(encoding="utf-8"))
    out = {}
    for c in data["cameras"]:
        slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", c["name"].lower())).strip("-")
        diag = (c["sensor_w"] ** 2 + c["sensor_h"] ** 2) ** 0.5
        out[slug] = {
            "name": c["name"],
            "coc": diag / 1500.0,
            "crop": ((36.0 ** 2 + 24.0 ** 2) ** 0.5) / diag,
        }
    return out


def run_claims():
    """Extract the two published sensor numbers from each camera page and check
    them against data/cameras.json. Ground truth is computed, not judged."""
    cams = load_cameras()
    out = []
    for p in sorted(ROOT.glob("pages/cameras/*.html")):
        cam = cams.get(p.stem)
        if not cam:
            continue
        html = p.read_text(encoding="utf-8", errors="replace")
        txt = body_text(html)
        cands = []
        for m in re.findall(r"\d+\.\d+", txt):
            if m not in cands:
                cands.append(m)
        cands = cands[:30]
        if len(cands) < 3:
            continue
        qs = {
            "coc": {
                "type": "choice",
                "instructions": {
                    "question": "Which of these numbers is the circle of confusion this page uses as the sharpness yardstick for its depth of field math?",
                    "inspect": "`page.text` and `page.candidates`",
                    "focus": "The page names the circle of confusion next to its value. Do not confuse it with pixel pitch or a depth of field limit.",
                },
                "criteria": {c: "the value " + c for c in cands},
            },
            "crop": {
                "type": "choice",
                "instructions": {
                    "question": "Which of these numbers is this camera's crop factor relative to a full frame sensor?",
                    "inspect": "`page.text` and `page.candidates`",
                    "focus": "A crop factor for these bodies sits between 1.0 and 8.0.",
                },
                "criteria": {c: "the value " + c for c in cands},
            },
        }
        res = call("claim:" + p.stem, {"page": {"text": txt, "candidates": cands}}, qs)
        a = res.get("answers") or {}
        pick_coc = (a.get("coc") or {}).get("choice")
        pick_crop = (a.get("crop") or {}).get("choice")
        # code incumbent: the number next to the label, either spelling, either side
        m = re.search(r"(?:circle of confusion|\bCoC\b)[^0-9]{0,24}(\d+(?:\.\d+)?)", txt, re.I)
        regex_coc = m.group(1) if m else None
        m2 = (re.search(r"(\d+(?:\.\d+)?)\s*(?:×|x|\*)?\s*crop factor", txt, re.I)
              or re.search(r"crop factor[^0-9]{0,24}(\d+(?:\.\d+)?)", txt, re.I))
        regex_crop = m2.group(1) if m2 else None

        def ok(pick, truth, tol):
            try:
                return abs(float(pick) - truth) <= tol
            except (TypeError, ValueError):
                return False

        out.append({
            "page": p.stem, "camera": cam["name"],
            "coc_truth": round(cam["coc"], 4), "coc_jev": pick_coc,
            "coc_ok": ok(pick_coc, cam["coc"], 0.0006),
            "coc_regex": regex_coc, "coc_regex_ok": ok(regex_coc, cam["coc"], 0.0006),
            "crop_truth": round(cam["crop"], 2), "crop_jev": pick_crop,
            "crop_ok": ok(pick_crop, cam["crop"], 0.006),
            "crop_regex": regex_crop, "crop_regex_ok": ok(regex_crop, cam["crop"], 0.006),
            "candidates": len(cands),
        })
    return out


def summarize_claims(rows):
    print("\n=== 3. published number check, %d camera pages (truth from cameras.json) ===" % len(rows))
    if not rows:
        print("no rows")
        return
    for field, label in (("coc", "circle of confusion"), ("crop", "crop factor")):
        j = sum(1 for r in rows if r[field + "_ok"])
        g = sum(1 for r in rows if r[field + "_regex_ok"])
        print("  %-20s jev %2d/%d (%.0f%%) | regex incumbent %2d/%d (%.0f%%)" %
              (label, j, len(rows), 100 * j / len(rows), g, len(rows), 100 * g / len(rows)))
    bad = [r for r in rows if not (r["coc_ok"] and r["crop_ok"])]
    if bad:
        print("  misses:")
        for r in bad[:15]:
            print("    %-24s coc jev=%s truth=%s | crop jev=%s truth=%s" %
                  (r["page"], r["coc_jev"], r["coc_truth"], r["crop_jev"], r["crop_truth"]))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "diff"):
        summarize_diff(run_diff())
    if which == "diff2":
        print("--- same 32 documents, single condition, code-verified label ---")
        summarize_diff(run_diff(eq_questions(), "diff2"))
    if which in ("all", "route"):
        summarize_routing(run_routing())
    if which == "route3":
        print("--- same 14 queries, with the site's own page conventions stated ---")
        summarize_routing(run_routing(hinted=True))
    if which in ("all", "claim"):
        summarize_claims(run_claims())
    print("\ncache:", CACHE_PATH, "| calls cached:", len(CACHE))

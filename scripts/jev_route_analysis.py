"""Score the Jev GSC routing run: accuracy, baselines, confidence bands, disagreement lists.

Works from the raw cache of API answers (scripts/jev_routing_gsc_results.json) so nothing
depends on the order the runner printed things in.

    python scripts/jev_route_analysis.py           # unhinted
    python scripts/jev_route_analysis.py hinted
"""

import collections
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "scripts" / "jev_routing_gsc_results.json"


def url_to_path(u):
    p = re.sub(r"^https?://(www\.)?shuttermath\.com", "", u).split("?")[0].split("#")[0]
    if p in ("", "/"):
        return "/index.html"
    if not p.startswith("/"):
        p = "/" + p
    if p.endswith("/"):
        p += "index.html"
    if not p.endswith(".html"):
        p += "/index.html"
    return p


def candidate_pages():
    pages = []
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("embed/", ".git/", "google")) or rel in ("404.html",):
            continue
        html = p.read_text(encoding="utf-8", errors="replace")
        t = re.search(r"<title>(.*?)</title>", html, re.S)
        d = re.search(r'name="description"\s+content="(.*?)"', html, re.S)
        pages.append({"path": "/" + rel,
                      "title": (t.group(1).strip() if t else p.stem).split("|")[0].strip(),
                      "desc": re.sub(r"\s+", " ", d.group(1)).strip() if d else ""})
    return pages


def baseline(query, pages, use_desc=False):
    qw = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not qw:
        return None, []
    scored = []
    for p in pages:
        hay = p["path"] + " " + p["title"] + (" " + p["desc"] if use_desc else "")
        hw = set(re.findall(r"[a-z0-9]+", hay.lower()))
        scored.append((len(qw & hw) / len(qw), p["path"]))
    scored.sort(key=lambda kv: (-kv[0], kv[1]))
    return scored[0][1], [s[1] for s in scored[:3]]


def rows(hinted):
    cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    gsc = json.loads((ROOT / "data" / "gsc_query_page.json").read_text(encoding="utf-8"))
    pages = candidate_pages()
    paths = {p["path"] for p in pages}
    byq = collections.defaultdict(list)
    for r in gsc["rows"]:
        q, u = r["keys"][0].strip(), r["keys"][1]
        if not q or "shuttermath" in q.lower():
            continue
        byq[q].append({"path": url_to_path(u), "impressions": r["impressions"],
                       "clicks": r["clicks"], "position": r["position"]})
    declared = {}
    track = ROOT / "data" / "serp_track.csv"
    if track.exists():
        for row in csv.DictReader(track.open(encoding="utf-8")):
            if row.get("query") and row.get("target_page"):
                declared[row["query"].strip()] = row["target_page"].strip()
    prefix = "gsc:routeh:" if hinted else "gsc:route:"
    out, missing = [], 0
    for q, hits in byq.items():
        res = cached.get(prefix + q)
        if not res:
            missing += 1
            continue
        hits.sort(key=lambda h: -h["impressions"])
        a = (res.get("answers") or {}).get("intended_page") or {}
        probs = a.get("probabilities") or {}
        b1, b3 = baseline(q, pages)
        b1d, _ = baseline(q, pages, use_desc=True)
        out.append({
            "query": q, "label": hits[0]["path"], "label_impr": hits[0]["impressions"],
            "n_served": len(hits), "others": [h["path"] for h in hits[1:]],
            "declared": declared.get(q, ""), "on_ballot": hits[0]["path"] in paths,
            "jev": a.get("choice"), "conf": a.get("confidence"),
            "top3": [k for k, _ in sorted(probs.items(), key=lambda kv: -kv[1])[:3]],
            "base": b1, "base3": b3, "base_desc": b1d,
            "okens": (res.get("usage") or {}).get("input_tokens", 0),
        })
    out.sort(key=lambda r: -r["label_impr"])
    print("scored %d queries (no cached answer for %d)" % (len(out), missing))
    return out


def tier(rows_sub, title):
    n = len(rows_sub)
    if not n:
        return
    def pct(x):
        return 100 * x / n
    j1 = sum(1 for r in rows_sub if r["jev"] == r["label"])
    j3 = sum(1 for r in rows_sub if r["label"] in r["top3"])
    b1 = sum(1 for r in rows_sub if r["base"] == r["label"])
    b3 = sum(1 for r in rows_sub if r["label"] in r["base3"])
    b1d = sum(1 for r in rows_sub if r["base_desc"] == r["label"])
    fail = [r for r in rows_sub if r["base_desc"] != r["label"] and r["base"] != r["label"]]
    print("\n%s  n=%d" % (title, n))
    print("  top-1: jev %d (%.1f%%) | baseline path+title %d (%.1f%%) | baseline +desc %d (%.1f%%)"
          % (j1, pct(j1), b1, pct(b1), b1d, pct(b1d)))
    print("  top-3: jev %d (%.1f%%) | baseline path+title %d (%.1f%%)" % (j3, pct(j3), b3, pct(b3)))
    if fail:
        rec = sum(1 for r in fail if r["jev"] == r["label"])
        print("  on the %d queries BOTH baselines miss: jev top-1 %d (%.1f%%)"
              % (len(fail), rec, 100 * rec / len(fail)))
    print("  both wrong: %d (%.1f%%)" % (sum(1 for r in rows_sub
                                             if r["jev"] != r["label"] and r["base"] != r["label"]),
                                          pct(sum(1 for r in rows_sub
                                                  if r["jev"] != r["label"] and r["base"] != r["label"]))))
    print("  jev agrees with baseline: %.0f%%" % pct(sum(1 for r in rows_sub
                                                        if r["jev"] == r["base"])))


def bands(rows_sub):
    out = collections.defaultdict(lambda: [0, 0])
    for r in rows_sub:
        c = r["conf"]
        if c is None:
            continue
        b = ("<0.40" if c < 0.4 else "0.40-0.49" if c < 0.5 else "0.50-0.69" if c < 0.7
             else "0.70-0.89" if c < 0.9 else "0.90-1.00")
        out[b][1] += 1
        if r["jev"] == r["label"]:
            out[b][0] += 1
    print("\n--- accuracy by Jev's own confidence (>=2 impressions) ---")
    for b in ("<0.40", "0.40-0.49", "0.50-0.69", "0.70-0.89", "0.90-1.00"):
        c, n = out[b]
        if n:
            print("  conf %-9s n=%3d  correct %3d (%5.1f%%)" % (b, n, c, 100 * c / n))


def main():
    hinted = len(sys.argv) > 1 and sys.argv[1] == "hinted"
    allrows = rows(hinted)
    print("mode:", "hinted" if hinted else "unhinted")
    off = [r for r in allrows if not r["on_ballot"]]
    home = [r for r in allrows if r["label"] == "/index.html"]
    print("labels not on the ballot: %d | labels that are the homepage (excluded): %d"
          % (len(off), len(home)))
    scored = [r for r in allrows if r["on_ballot"] and r["label"] != "/index.html"]
    tier(scored, "ALL queries")
    tier([r for r in scored if r["label_impr"] >= 2], "queries with >=2 impressions")
    tier([r for r in scored if r["label_impr"] >= 5], "queries with >=5 impressions")
    bands([r for r in scored if r["label_impr"] >= 2])

    dec = [r for r in scored if r["declared"]]
    print("\n--- the queries the site itself declared a target for (n=%d) ---" % len(dec))
    print("  GSC label == declared: %d | jev == declared: %d | baseline == declared: %d"
          % (sum(1 for r in dec if r["label"] == r["declared"]),
             sum(1 for r in dec if r["jev"] == r["declared"]),
             sum(1 for r in dec if r["base"] == r["declared"])))
    for r in dec:
        if r["label"] != r["declared"] or r["jev"] != r["declared"]:
            print("    %-30s declared=%-42s gsc=%-34s jev=%s" %
                  (r["query"][:30], r["declared"], r["label"], r["jev"]))

    tok = sum(r["okens"] for r in allrows)
    print("\ntokens: %.2fM input over %d calls (%.0f tokens/call)"
          % (tok / 1e6, len(allrows), tok / max(1, len(allrows))))
    print("calls where no answer came back: %d" % sum(1 for r in allrows if not r["jev"]))

    dif = [r for r in scored if r["jev"] and r["jev"] != r["label"] and r["label_impr"] >= 5]
    print("\n--- Google serves A, jev picks B (>=5 impressions, n=%d) ---" % len(dif))
    for r in dif:
        print("  %-34s imps=%-3d served=%-40s jev=%-40s conf=%s"
              % (r["query"][:34], r["label_impr"], r["label"], r["jev"], r["conf"]))


if __name__ == "__main__":
    main()

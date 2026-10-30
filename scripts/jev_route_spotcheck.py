"""Independent check of Jev's routing picks: does the page it chose actually cover the query?

For each disputed query (Google serves page A, Jev picks page B, A != B) count how many of
the query's content words appear in each page's own body text, and print a snippet around the
match. This is a check on the PICK, not on the label: a pick whose page never mentions the
query's subject is a wrong pick whatever the label says, and vice versa.

Reads scripts/jev_routing_gsc_scored.json (written by jev_routing_gsc.py run).

    python scripts/jev_route_spotcheck.py 5 40
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOP = set("""a an and are at be by can do does for from how in is it its of on or that the this to
what when where which who why with you your my me i calculator chart formula table photography
photo camera cameras best vs use using""".split())


def body(path):
    p = ROOT / path.lstrip("/")
    if not p.exists():
        return ""
    html = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    frag = m.group(1) if m else html
    frag = re.sub(r"<(script|style|nav)\b.*?</\1>", " ", frag, flags=re.S | re.I)
    frag = re.sub(r"<[^>]+>", " ", frag)
    frag = re.sub(r"&[a-z]+;", " ", frag)
    return re.sub(r"\s+", " ", frag).strip()


def coverage(q, txt):
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in STOP and len(w) > 2]
    if not words:
        return 0, 0, []
    low = txt.lower()
    hit = [w for w in words if w in low]
    return len(hit), len(words), hit


def load_rows():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "jev_route_analysis", str(ROOT / "scripts" / "jev_route_analysis.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.rows(False)


def main():
    min_imp = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    rows = load_rows()
    byq = {}
    for r in rows:
        if r["label_impr"] < min_imp or not r.get("jev"):
            continue
        if r["jev"] == r["label"] or r["label"] == "/index.html":
            continue
        prev = byq.get(r["query"])
        if prev is None or r["label_impr"] > prev["label_impr"]:
            byq[r["query"]] = r
    diffs = sorted(byq.values(), key=lambda r: -r["label_impr"])
    print("disputed queries with >=%d impressions: %d\n" % (min_imp, len(diffs)))
    cache = {}
    jev_better = served_better = tie = 0
    for r in diffs[:limit]:
        for path in (r["label"], r["jev"]):
            if path not in cache and not path.startswith("/index"):
                cache[path] = body(path)
        q = r["query"]
        cs, ns, hs = coverage(q, cache.get(r["label"], ""))
        cj, _, hj = coverage(q, cache.get(r["jev"], ""))
        flag = "JEV" if cj > cs else ("served" if cs > cj else "tie")
        jev_better += flag == "JEV"
        served_better += flag == "served"
        tie += flag == "tie"
        print("%-34s imps=%-3d served=%-32s %d/%d %s" %
              (q[:34], r["label_impr"], r["label"], cs, ns, hs))
        print("%-34s        jev   =%-32s %d/%d %s   -> %s" %
              ("", r["jev"], cj, len(hj), hj, flag))
        print()
    print("body-term coverage favours: jev %d | served page %d | tie %d (of %d)"
          % (jev_better, served_better, tie, min(limit, len(diffs))))


if __name__ == "__main__":
    main()

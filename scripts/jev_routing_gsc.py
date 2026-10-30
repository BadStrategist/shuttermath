"""Shadow evaluation: route real Google Search Console queries to the right ShutterMath page.

Label = the page Google itself currently attributes the query to (from the GSC
query+page dimension). That is a real, external label, not my opinion. Where the
label is the homepage the intent owner is ambiguous, so those rows are excluded
from the accuracy figure and reported separately.

The point of the run: the lexical baseline (word overlap between the query and the
page path/title) is free. Report Jev's accuracy on the WHOLE set, then on the
SUBSET where the free baseline is wrong. The second number is the value: extra
correct routes bought for the price of one API call each.

Nothing here writes to the site. Results land in
scripts/jev_routing_gsc_results.json (cache, keyed per variant+query).

Usage:
    python scripts/jev_routing_gsc.py fetch   # pull GSC query+page rows (needs ADC)
    python scripts/jev_routing_gsc.py run     # Jev, unhinted, all queries
    python scripts/jev_routing_gsc.py hinted  # Jev with the site-convention hint
    python scripts/jev_routing_gsc.py report  # score whatever is cached
"""

import csv
import collections
import concurrent.futures as futures
import datetime
import json
import os
import pathlib
import re
import sys
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
GSC_PATH = ROOT / "data" / "gsc_query_page.json"
CACHE_PATH = ROOT / "scripts" / "jev_routing_gsc_results.json"
SITE = "sc-domain:shuttermath.com"
WORKERS = 8


def api_key():
    envp = pathlib.Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"
    for line in envp.read_text(encoding="utf-8").splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("TYPESAFE_API_KEY not found in hermes/.env")


KEY = api_key()
CACHE = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
CACHE_LOCK = threading.Lock()
NEW_TOKENS = [0]


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
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        out = {"error": str(last)}
    if "usage" in out:
        NEW_TOKENS[0] += (out.get("usage") or {}).get("input_tokens", 0)
    with CACHE_LOCK:
        CACHE[key] = out
        save_cache()
    return out


# ---------------------------------------------------------------- GSC pull

def fetch_gsc():
    from google.auth import default
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = default(scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    s = AuthorizedSession(creds)
    end = datetime.date.today() - datetime.timedelta(days=2)
    start = end - datetime.timedelta(days=400)
    url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
           + SITE.replace(":", "%3A") + "/searchAnalytics/query")
    r = s.post(url, json={"startDate": str(start), "endDate": str(end),
                          "dimensions": ["query", "page"], "rowLimit": 25000})
    if r.status_code != 200:
        raise SystemExit("GSC %s %s" % (r.status_code, r.text[:400]))
    rows = r.json().get("rows", [])
    GSC_PATH.write_text(json.dumps({"start": str(start), "end": str(end), "rows": rows},
                                   indent=1), encoding="utf-8")
    print("wrote", GSC_PATH, "rows", len(rows))


# ------------------------------------------------------------ site ballot

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
        pages.append({
            "path": "/" + rel,
            "title": (t.group(1).strip() if t else p.stem).split("|")[0].strip(),
            "desc": re.sub(r"\s+", " ", d.group(1)).strip() if d else "",
        })
    return pages


def queries():
    data = json.loads(GSC_PATH.read_text(encoding="utf-8"))
    byq = collections.defaultdict(list)
    for r in data["rows"]:
        q, u = r["keys"][0].strip(), r["keys"][1]
        if not q or "shuttermath" in q.lower():
            continue
        byq[q].append({"path": url_to_path(u), "impressions": r["impressions"],
                       "clicks": r["clicks"], "position": r["position"]})
    out = []
    seen = set()
    # queries the site itself declared a target for, from serp_track.csv
    declared = {}
    track = ROOT / "data" / "serp_track.csv"
    if track.exists():
        for row in csv.DictReader(track.open(encoding="utf-8")):
            if row.get("query") and row.get("target_page"):
                declared[row["query"].strip()] = row["target_page"].strip()
    for q, hits in byq.items():
        hits.sort(key=lambda h: -h["impressions"])
        out.append({"query": q, "label": hits[0]["path"],
                    "label_impressions": hits[0]["impressions"],
                    "n_pages_served": len(hits),
                    "other_pages": [h["path"] for h in hits[1:]],
                    "declared_target": declared.get(q, "")})
    out.sort(key=lambda r: -r["label_impressions"])
    return out


HINT = ("This site has two kinds of page. Paths under /tools/ are interactive calculators. "
        "Paths under /pages/ are reference or explainer articles. The site's own target for a "
        "query that names a calculator, a chart or a formula is the matching calculator or chart "
        "page, not the topic overview and not an index page.")


def ask(query, pages, criteria, hinted):
    instructions = {
        "question": "Which page of this site is the intended landing page for this search query?",
        "inspect": "`query` and `site_pages`",
        "focus": "Match the query's topic to the page that owns that topic.",
    }
    if hinted:
        instructions["site_conventions"] = HINT
    return {
        "intended_page": {
            "type": "choice",
            "instructions": instructions,
            "criteria": criteria,
        },
    }


def run(hinted=False):
    pages = candidate_pages()
    criteria = {p["path"]: (p["title"] + " :: " + p["desc"]) for p in pages}
    rows = queries()
    prefix = "gsc:route:" if not hinted else "gsc:routeh:"

    def work(row):
        res = call(prefix + row["query"], {"query": row["query"], "site_pages": pages},
                   ask(row["query"], pages, criteria, hinted))
        return res

    t0 = time.time()
    with futures.ThreadPoolExecutor(WORKERS) as ex:
        answers = list(ex.map(work, rows))
    for row, res in zip(rows, answers):
        row["jev"] = res
    print("ran %d queries in %.0fs, candidates %d, new input tokens %d"
          % (len(rows), time.time() - t0, len(pages), NEW_TOKENS[0]))
    return rows, pages, criteria


# ------------------------------------------------------------- baselines

def baseline_pick(query, pages, use_desc=False):
    qw = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not qw:
        return None, []
    scored = []
    for p in pages:
        hay = p["path"] + " " + p["title"] + (" " + p["desc"] if use_desc else "")
        hw = set(re.findall(r"[a-z0-9]+", hay.lower()))
        score = len(qw & hw) / len(qw)
        scored.append((score, p["path"]))
    scored.sort(key=lambda kv: (-kv[0], kv[1]))
    return scored[0][1], [s[1] for s in scored[:3]]


# --------------------------------------------------------------- report

def report(rows, pages, criteria, hinted=False):
    name = "hinted" if hinted else "unhinted"
    print("\n=== Jev routes real GSC queries to ShutterMath pages (%s) ===" % name)
    scored, uncovered, jev_err = [], 0, 0
    for r in rows:
        if r["label"] not in criteria:
            uncovered += 1
            continue
        a = (r.get("jev") or {}).get("answers") or {}
        if not a:
            jev_err += 1
        pick = (a.get("intended_page") or {}).get("choice")
        probs = (a.get("intended_page") or {}).get("probabilities") or {}
        top3 = [k for k, _ in sorted(probs.items(), key=lambda kv: -kv[1])[:3]]
        b1, b3 = baseline_pick(r["query"], pages)
        b1d, b3d = baseline_pick(r["query"], pages, use_desc=True)
        r.update({"jev_pick": pick, "jev_conf": (a.get("intended_page") or {}).get("confidence"),
                  "jev_top3": top3, "base_pick": b1, "base_top3": b3,
                  "base_pick_desc": b1d, "base_top3_desc": b3d,
                  "home_label": r["label"] == "/index.html"})
        scored.append(r)
    print("labels not on the ballot: %d | calls with no answer: %d | scored: %d"
          % (uncovered, jev_err, len(scored)))
    scored = [r for r in scored if not r["home_label"]]
    print("labels that are the homepage (excluded, ambiguous owner): %d"
          % sum(1 for r in rows if r["label"] == "/index.html"))

    def tier(rows_sub, title):
        n = len(rows_sub)
        if not n:
            return
        j1 = sum(1 for r in rows_sub if r["jev_pick"] == r["label"])
        j3 = sum(1 for r in rows_sub if r["label"] in r["jev_top3"])
        b1 = sum(1 for r in rows_sub if r["base_pick"] == r["label"])
        b1d = sum(1 for r in rows_sub if r["base_pick_desc"] == r["label"])
        print("\n%s  n=%d" % (title, n))
        print("  top-1  jev %3d/%d (%5.1f%%) | lexical(path+title) %3d/%d (%5.1f%%) | lexical(+desc) %3d/%d (%5.1f%%)"
              % (j1, n, 100 * j1 / n, b1, n, 100 * b1 / n, b1d, n, 100 * b1d / n))
        print("  top-3  jev %3d/%d (%5.1f%%) | lexical(path+title) %3d/%d (%5.1f%%)"
              % (j3, n, 100 * j3 / n,
                 sum(1 for r in rows_sub if r["label"] in r["base_top3"]), n,
                 100 * sum(1 for r in rows_sub if r["label"] in r["base_top3"]) / n))
        # the value subset: baseline wrong on top-1, strongest baseline
        fail = [r for r in rows_sub if r["base_pick_desc"] != r["label"]]
        if fail:
            rec = sum(1 for r in fail if r["jev_pick"] == r["label"])
            rec3 = sum(1 for r in fail if r["label"] in r["jev_top3"])
            print("  baseline wrong (n=%d): jev recovers top-1 %d (%.1f%%), in its top-3 %d (%.1f%%)"
                  % (len(fail), rec, 100 * rec / len(fail), rec3, 100 * rec3 / len(fail)))
        both_wrong = [r for r in rows_sub
                      if r["base_pick_desc"] != r["label"] and r["jev_pick"] != r["label"]]
        print("  both wrong: %d (%.1f%%)" % (len(both_wrong), 100 * len(both_wrong) / n))
        agree = sum(1 for r in rows_sub if r["jev_pick"] == r["base_pick_desc"])
        print("  jev agrees with the baseline pick: %d (%.0f%%)" % (agree, 100 * agree / n))

    tier(scored, "ALL queries")
    tier([r for r in scored if r["label_impressions"] >= 2], "queries with >=2 impressions")
    tier([r for r in scored if r["label_impressions"] >= 5], "queries with >=5 impressions")

    dec = [r for r in scored if r["declared_target"]]
    if dec:
        print("\n--- label validation: the 14 queries the site itself declared a target for ---")
        okg = sum(1 for r in dec if r["label"] == r["declared_target"])
        okj = sum(1 for r in dec if r["jev_pick"] == r["declared_target"])
        okb = sum(1 for r in dec if r["base_pick_desc"] == r["declared_target"])
        print("  GSC label == declared target: %d/%d" % (okg, len(dec)))
        print("  jev matches declared target:  %d/%d" % (okj, len(dec)))
        print("  baseline matches declared:    %d/%d" % (okb, len(dec)))
        for r in dec:
            print("    %-30s declared=%-34s gsc=%-34s jev=%s" %
                  (r["query"][:30], r["declared_target"], r["label"], r["jev_pick"]))

    # actionable: queries where jev's pick differs from the page Google serves
    diff = [r for r in scored if r["jev_pick"] and r["jev_pick"] != r["label"]
            and r["label_impressions"] >= 2]
    print("\n--- where Google serves one page and Jev picks another (>=2 impressions, n=%d) ---"
          % len(diff))
    for r in sorted(diff, key=lambda r: -r["label_impressions"])[:40]:
        print("  %-38s served=%-34s jev=%-34s conf=%s" %
              (r["query"][:38], r["label"], r["jev_pick"], r["jev_conf"]))
    can = [r for r in scored if r["n_pages_served"] > 1 and r["label_impressions"] >= 2]
    print("\n--- queries Google splits across more than one page (cannibalization, >=2 imps, n=%d) ---"
          % len(can))
    for r in sorted(can, key=lambda r: -r["label_impressions"])[:20]:
        print("  %-38s %s + %s" % (r["query"][:38], r["label"], ", ".join(r["other_pages"][:3])))
    return scored


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "report"
    if which == "fetch":
        fetch_gsc()
    if which == "run":
        rows, pages, criteria = run(False)
        json.dump(rows, (ROOT / "scripts" / "jev_routing_gsc_scored.json").open("w", encoding="utf-8"),
                  indent=1)
        report(rows, pages, criteria, False)
    if which == "hinted":
        rows, pages, criteria = run(True)
        json.dump(rows, (ROOT / "scripts" / "jev_routing_gsc_scored_hinted.json").open("w", encoding="utf-8"),
                  indent=1)
        report(rows, pages, criteria, True)
    if which == "report":
        rows, pages, criteria = run(False)
        report(rows, pages, criteria, False)
    print("\ncache:", CACHE_PATH, "| entries:", len(CACHE))

#!/usr/bin/env python3
"""ShutterMath backlink outreach sender.

Reads targets from outreach_targets.json, sends personalized, rate-limited
cold emails via SMTP, and logs every send to outreach_sent.json.

Requires env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, OUTREACH_FROM,
OUTREACH_NAME. Configure via config in script or a .env file.

This is a READY-TO-FIRE script: point it at a working SMTP channel and run.
Safely no-ops if SMTP creds are absent (so it never falsely "sends").
"""
import json, os, smtplib, sys, time, argparse, ssl
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = HERE / "outreach_targets.json"
LOG = HERE / "outreach_sent.json"

# Default pitch template (individual target overrides in JSON)
DEFAULT_SUBJECT = "Free photography calculator for your {page_type}"
DEFAULT_BODY = """Hi {name},

I noticed you maintain {page} — a great resource for photographers. I built ShutterMath, a free, no-signup, no-watermark photography calculator suite: depth of field, hyperfocal, ND filters, star-trails (500/NPF rule), flash guide number, and astro pixel scale. It's accurate to the exact sensor of 100+ cameras, has no ads, and is 100% free forever.

It would fit naturally on your {page_type} alongside the tools you already recommend. It's exactly the kind of thing I wanted as a photographer, so I built it without paywalls or accounts.

Happy to answer any questions — and no pressure at all. Thanks for the resource you've put together for the community.

Best,
Tyler
ShutterMath — https://shuttermath.com
"""

def load_targets():
    if not TARGETS.exists():
        print("[dry-run] No outreach_targets.json — nothing to send.")
        return []
    return json.loads(TARGETS.read_text(encoding="utf-8"))

def load_sent():
    if not LOG.exists():
        return {}
    try:
        return json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_creds():
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": os.environ.get("SMTP_USER"),
        "pass": os.environ.get("SMTP_PASS"),
        "frm": os.environ.get("OUTREACH_FROM"),
        "name": os.environ.get("OUTREACH_NAME", "Tyler"),
    }

def build_message(t, creds):
    subj = t.get("subject", DEFAULT_SUBJECT).format(**t)
    body = t.get("body", DEFAULT_BODY).format(**t)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subj
    msg["From"] = f"{creds['name']} <{creds['frm']}>"
    msg["To"] = t["to"]
    msg["Reply-To"] = creds["frm"]
    return msg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print what would be sent, send nothing")
    ap.add_argument("--limit", type=int, default=0, help="Max emails to send this run (0=all)")
    ap.add_argument("--target", help="Send only to this site (match)")
    args = ap.parse_args()

    creds = load_creds()
    targets = load_targets()
    sent = load_sent()
    if not targets:
        return 0

    if args.dry_run or not all([creds["host"], creds["user"], creds["pass"], creds["frm"]]):
        print("DRY-RUN or no SMTP creds — will NOT send. Configure SMTP_HOST/PORT/USER/PASS/OUTREACH_FROM to enable.")
        shown = 0
        for t in targets:
            if args.target and args.target.lower() not in t["site"].lower():
                continue
            if args.limit and shown >= args.limit:
                print(f"  [limit] preview capped at --limit={args.limit}")
                break
            status = "SENT" if t.get("to") in sent else "pending"
            # .get() fallback: a target may omit "subject" and rely on
            # DEFAULT_SUBJECT, exactly as build_message does — indexing here
            # crashed the advertised safe preview with KeyError: 'subject'.
            print(f"  [{status}] {t['site']:<28} -> {t['to']:<40} "
                  f"{t.get('subject', DEFAULT_SUBJECT).format(**t)}")
            shown += 1
        return 0

    ctx = ssl.create_default_context()
    n = 0
    with smtplib.SMTP_SSL(creds["host"], creds["port"], context=ctx, timeout=60) as srv:
        srv.login(creds["user"], creds["pass"])
        for t in targets:
            if args.target and args.target.lower() not in t["site"].lower():
                continue
            # --limit was declared and documented ("rate-limited") but never
            # read, so --limit=N sent to every target. Enforce it here.
            if args.limit and n >= args.limit:
                print(f"  [limit] reached --limit={args.limit} — stopping this run")
                break
            if t.get("to") in sent:
                print(f"  [skip] {t['site']} already sent")
                continue
            msg = build_message(t, creds)
            srv.sendmail(creds["frm"], t["to"], msg.as_string())
            sent[t["to"]] = {
                "site": t["site"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
                # .get() fallback — a KeyError here fires AFTER the mail is sent,
                # so the log write would fail and the next run would re-send the
                # same address (double-send).
                "subject": t.get("subject", DEFAULT_SUBJECT),
            }
            LOG.write_text(json.dumps(sent, indent=2), encoding="utf-8")
            n += 1
            print(f"  [SENT] {t['site']} -> {t['to']}")
            time.sleep(max(10, int(os.environ.get("OUTREACH_DELAY", "45"))))  # polite throttle
    print(f"Sent {n} this run. Total logged: {len(sent)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate the Google Search Console HTML verification file for ShutterMath.

Usage (from the photography-calc repo root):
    python scripts/gsc-verify.py <TOKEN>

Google gives you a token like "aB3xYz9Qw..." when you add a property in
Search Console (HTML file method). This writes google<TOKEN>.html at the
repo root. Commit + push it, then click Verify in Search Console.

If you prefer the meta-tag method instead, skip this and paste the meta tag
into index.html <head> — same effect, but the file method is cleaner for a
static site.
"""
import sys, os

def main():
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1].strip()
    if not token.isalnum():
        print("Token should be alphanumeric (looks like: aB3xYz9Qw). Got:", repr(token))
        sys.exit(1)
    filename = f"google{token}.html"
    content = (
        "<!-- google-site-verification: google" + token + " -->\n"
        "<!DOCTYPE html>\n<html>\n<head>\n"
        '<meta charset="utf-8">\n<title>Verification</title>\n'
        '<meta name="google-site-verification" content="google' + token + '">\n'
        "</head>\n<body>\n<p>ShutterMath verification file.</p>\n</body>\n</html>\n"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {filename}. Commit + push, then click Verify in Search Console.")
    print("After verifying, submit the sitemap: https://shuttermath.com/sitemap.xml")

if __name__ == "__main__":
    main()

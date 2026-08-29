"""
Multi-Platform New-VDP Monitor (H1 + Intigriti)
-------------------------------------------------
Checks HackerOne (official Hacker API) and Intigriti (public programs
page) for newly-appeared programs, and prints a categorized report.

WHY BUGCROWD ISN'T HERE:
Bugcrowd's public engagements listing now requires you to be logged
into your Researcher Dashboard -- there is no unauthenticated public
list, and their official API is customer/org-owner only. Faking a
logged-in scrape means storing your session cookie and re-auth'ing
every time it expires -- fragile and not worth automating. Just check
https://bugcrowd.com/engagements manually, once a day, logged in.
This script will remind you to do that every run.

SETUP:
1. HackerOne: generate an API token (Settings -> API Token), then:
     $env:H1_USERNAME='malikdishan'
     $env:H1_API_TOKEN='your_token_here'
2. Intigriti needs no auth -- public page.
3. Run:  python program_monitor.py
   (or double-click run_monitor.bat, same as before)

Every run:
- Pulls current H1 program list (full pagination) + current Intigriti
  first-3-pages listing (newest-sorted, so new ones are always near
  the top -- no need to paginate the whole site).
- Diffs against what's been seen before (seen_programs.json).
- Prints new ones, categorized by platform, with an "AGE" hint:
    H1        -> no public timestamp, so "new" = first time seen by
                 this script (run it regularly, don't rely on a single
                 check after days of not running it)
    Intigriti -> honors their own "New" badge, which IS a real signal
                 from their side, not just a diff artifact
"""

import requests
import time
import os
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup

H1_USERNAME = os.environ.get("H1_USERNAME", "<YOUR_USERNAME>")
H1_API_TOKEN = os.environ.get("H1_API_TOKEN", "<YOUR_API_TOKEN>")

H1_PROGRAMS_ENDPOINT = "https://api.hackerone.com/v1/hackers/programs"
INTIGRITI_LIST_URL = "https://www.intigriti.com/researchers/bug-bounty-programs"
INTIGRITI_PAGES_TO_CHECK = 3  # sorted newest-first by default; 3 pages is plenty

POLL_INTERVAL_SECONDS = 1800  # 30 minutes
SEEN_PROGRAMS_FILE = "seen_programs.json"
MAX_H1_PAGES = 50

HEADERS_H1 = {"Accept": "application/json"}
HEADERS_WEB = {"User-Agent": "Mozilla/5.0 (compatible; personal-vdp-monitor/1.0)"}


def load_seen():
    if os.path.exists(SEEN_PROGRAMS_FILE):
        with open(SEEN_PROGRAMS_FILE, "r") as f:
            return json.load(f)
    return {"h1": [], "intigriti": []}


def save_seen(seen):
    with open(SEEN_PROGRAMS_FILE, "w") as f:
        json.dump(seen, f)


# ---------------- HackerOne ----------------

def fetch_h1_programs():
    all_programs = []
    url = H1_PROGRAMS_ENDPOINT
    pages_fetched = 0

    while url and pages_fetched < MAX_H1_PAGES:
        try:
            response = requests.get(
                url, auth=(H1_USERNAME, H1_API_TOKEN),
                headers=HEADERS_H1, timeout=15
            )
        except requests.exceptions.RequestException as e:
            print(f"[H1] Request failed: {e}")
            return None

        if response.status_code == 401:
            print("[H1] Unauthorized -- check H1_USERNAME / H1_API_TOKEN.")
            return None
        elif response.status_code == 403:
            print("[H1] Forbidden -- token lacks access.")
            return None
        elif response.status_code == 429:
            print("[H1] Rate limited -- backing off this cycle.")
            return None
        elif response.status_code != 200:
            print(f"[H1] Unexpected status {response.status_code}: {response.text[:200]}")
            return None

        try:
            data = response.json()
        except ValueError:
            print("[H1] Response was not valid JSON.")
            return None

        for program in data.get("data", []):
            pid = program.get("id")
            attrs = program.get("attributes", {})
            all_programs.append({
                "id": pid,
                "name": attrs.get("name", "Unknown"),
                "handle": attrs.get("handle", ""),
                "state": attrs.get("state") or attrs.get("submission_state"),
                "offers_bounties": attrs.get("offers_bounties"),
                "open_scope": attrs.get("open_scope"),
                "gold_safe_harbor": attrs.get("gold_standard_safe_harbor"),
            })

        url = data.get("links", {}).get("next")
        pages_fetched += 1

    return all_programs


def h1_partial_signal(p):
    signals_passed = sum([
        p["offers_bounties"] is True,
        p["open_scope"] is True,
        p["gold_safe_harbor"] is True,
    ])
    if signals_passed == 3:
        return "3/3 partial signals -- worth a manual look"
    elif signals_passed == 2:
        return "2/3 partial signals -- maybe"
    return "low partial signal -- check manually if interested"


# ---------------- Intigriti ----------------

def fetch_intigriti_programs():
    """
    Scrapes the public, no-login-required programs listing, sorted
    newest-first by default. Only walks the first few pages since new
    programs surface at the top. Returns None on failure (site layout
    change, network error, etc.) -- treat that as "check manually this
    run", not as "no new programs".
    """
    programs = []
    try:
        for page in range(1, INTIGRITI_PAGES_TO_CHECK + 1):
            url = INTIGRITI_LIST_URL
            if page > 1:
                url = f"{INTIGRITI_LIST_URL}?programs_prod[page]={page}"
            resp = requests.get(url, headers=HEADERS_WEB, timeout=15)
            if resp.status_code != 200:
                print(f"[Intigriti] page {page}: HTTP {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            # Program cards: each has a link to /programs/<company>/<slug>
            for link in soup.select('a[href*="app.intigriti.com/programs/"]'):
                href = link.get("href", "")
                card = link.find_parent()
                # Walk up to find the block that contains the title + "New" badge
                block_text = card.get_text(" ", strip=True) if card else ""
                title_tag = link.find(["h3", "h4"]) or link
                name = title_tag.get_text(strip=True) if title_tag else href
                is_new = "New" in block_text.split(name)[-1][:40] if name in block_text else False
                programs.append({
                    "id": href,
                    "name": name,
                    "url": href,
                    "is_new_badge": bool(is_new),
                })
    except requests.exceptions.RequestException as e:
        print(f"[Intigriti] Request failed: {e}")
        return None
    except Exception as e:
        print(f"[Intigriti] Parse failed (site layout may have changed): {e}")
        return None

    # de-dupe by url, preserve order
    seen_urls = set()
    deduped = []
    for p in programs:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            deduped.append(p)
    return deduped


# ---------------- Combined run ----------------

def run_once(seen):
    print(f"\n===== Check @ {datetime.now(timezone.utc).isoformat()} =====")
    seen_h1 = set(seen.get("h1", []))
    seen_intigriti = set(seen.get("intigriti", []))

    new_h1_ids = []
    new_intigriti_ids = []

    # --- HackerOne ---
    h1_programs = fetch_h1_programs()
    if h1_programs is None:
        print("[H1] Skipped this cycle (fetch failed) -- previous seen-list kept.")
    else:
        h1_new = [p for p in h1_programs if p["id"] not in seen_h1]
        if h1_new:
            print(f"\n--- HackerOne: {len(h1_new)} new program(s) ---")
            for p in h1_new:
                print(f"  NEW  {p['name']}  ({h1_partial_signal(p)})")
                print(f"       https://hackerone.com/{p['handle']}")
                new_h1_ids.append(p["id"])
        else:
            print(f"[H1] No new programs. Tracking {len(h1_programs)} total.")
        seen_h1.update(p["id"] for p in h1_programs)

    # --- Intigriti ---
    intigriti_programs = fetch_intigriti_programs()
    if intigriti_programs is None:
        print("[Intigriti] Skipped this cycle (fetch/parse failed) -- check site manually this run.")
    else:
        intigriti_new = [p for p in intigriti_programs if p["id"] not in seen_intigriti]
        if intigriti_new:
            print(f"\n--- Intigriti: {len(intigriti_new)} new-to-you program(s) ---")
            for p in intigriti_new:
                badge = "site marks this NEW" if p["is_new_badge"] else "new to this script, no site badge"
                print(f"  NEW  {p['name']}  ({badge})")
                print(f"       {p['url']}")
                new_intigriti_ids.append(p["id"])
        else:
            print(f"[Intigriti] No new programs in top {INTIGRITI_PAGES_TO_CHECK} pages.")
        seen_intigriti.update(p["id"] for p in intigriti_programs)

    print("\n--- Bugcrowd ---")
    print("  Not automatable (requires login). Manually check: https://bugcrowd.com/engagements")

    return {"h1": list(seen_h1), "intigriti": list(seen_intigriti)}


def main():
    seen = load_seen()
    print(f"Starting monitor. Tracking {len(seen.get('h1', []))} H1 + "
          f"{len(seen.get('intigriti', []))} Intigriti known programs.")

    while True:
        seen = run_once(seen)
        save_seen(seen)
        print(f"\nCheck complete. Sleeping {POLL_INTERVAL_SECONDS}s.\n")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

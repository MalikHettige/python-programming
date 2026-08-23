"""
HackerOne New Program Monitor (v2)
------------------------------------
Polls the HackerOne Hacker API for newly launched public programs and
alerts you when new ones appear.

CONFIRMED BY TESTING (Aug 2026): /v1/hackers/programs does NOT support
sort=-started_accepting_at or any other tested sort param -- it always
returns results in the same fixed order (ascending internal id). So
"new program detection" works by pulling the FULL list every poll
(following pagination) and diffing against what's been seen before,
not by trusting a "newest first" ordering.

SETUP REQUIRED before running:
1. Generate an API token: HackerOne Settings -> API Token
2. In PowerShell, before running this script:
     $env:H1_USERNAME='your_username_here'
     $env:H1_API_TOKEN='your_token_here'
     python h1_program_monitor_v2.py

Rate limits (from HackerOne docs):
- Read operations: 600 requests / minute
- This script paginates the full program list every 30 min by default.
  Even with several pages, that's nowhere near the limit.
"""

import requests
import time
import os
import json
from datetime import datetime, timezone

H1_USERNAME = os.environ.get("H1_USERNAME", "<YOUR_USERNAME>")
H1_API_TOKEN = os.environ.get("H1_API_TOKEN", "<YOUR_API_TOKEN>")

PROGRAMS_ENDPOINT = "https://api.hackerone.com/v1/hackers/programs"

POLL_INTERVAL_SECONDS = 1800  # 30 minutes
SEEN_PROGRAMS_FILE = "seen_programs.json"
MAX_PAGES = 50  # safety cap so a bug can't cause infinite pagination

HEADERS = {
    "Accept": "application/json"
}


def load_seen_programs():
    if os.path.exists(SEEN_PROGRAMS_FILE):
        with open(SEEN_PROGRAMS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_programs(seen):
    with open(SEEN_PROGRAMS_FILE, "w") as f:
        json.dump(list(seen), f)


def fetch_all_programs():
    """
    Paginate through every page of /v1/hackers/programs and return a list of
    (id, name, state) tuples for ALL programs currently visible to this
    account. Follows 'links.next' until there isn't one, capped at
    MAX_PAGES as a safety net. Returns None on any request failure.
    """
    all_programs = []
    url = PROGRAMS_ENDPOINT
    pages_fetched = 0

    while url and pages_fetched < MAX_PAGES:
        try:
            response = requests.get(
                url,
                auth=(H1_USERNAME, H1_API_TOKEN),
                headers=HEADERS,
                timeout=15
            )
        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now(timezone.utc)}] Request failed: {e}")
            return None

        if response.status_code == 401:
            print("Unauthorized -- check your username/API token.")
            return None
        elif response.status_code == 403:
            print("Forbidden -- token doesn't have access to this resource.")
            return None
        elif response.status_code == 429:
            print("Rate limited -- backing off, will retry next cycle.")
            return None
        elif response.status_code != 200:
            print(f"Unexpected status {response.status_code}: {response.text[:200]}")
            return None

        try:
            data = response.json()
        except ValueError:
            print("Response was not valid JSON.")
            return None

        for program in data.get("data", []):
            program_id = program.get("id")
            attrs = program.get("attributes", {})
            name = attrs.get("name", "Unknown")
            state = attrs.get("state") or attrs.get("submission_state")
            handle = attrs.get("handle", "")
            offers_bounties = attrs.get("offers_bounties")
            open_scope = attrs.get("open_scope")
            gold_safe_harbor = attrs.get("gold_standard_safe_harbor")
            all_programs.append((program_id, name, state, handle,
                                  offers_bounties, open_scope, gold_safe_harbor))

        url = data.get("links", {}).get("next")
        pages_fetched += 1

    print(f"[{datetime.now(timezone.utc)}] Fetched {len(all_programs)} programs "
          f"across {pages_fetched} page(s).")
    return all_programs


def check_new_programs(seen_programs):
    all_programs = fetch_all_programs()
    if all_programs is None:
        # request failed somewhere -- don't wipe out what we've already seen
        return seen_programs

    new_seen = set(seen_programs)
    found_new = False

    for program_id, name, state, handle, offers_bounties, open_scope, gold_safe_harbor in all_programs:
        if program_id and program_id not in seen_programs:
            new_seen.add(program_id)
            found_new = True

            # PARTIAL pre-filter only -- this API does NOT return response
            # efficiency, resolved report count, or avg first-response time.
            # A pass here means it's WORTH manually checking on the H1
            # directory page against your real 5-Signal Screen -- it does
            # not mean the program has already passed the full screen.
            signals_passed = sum([
                offers_bounties is True,
                open_scope is True,
                gold_safe_harbor is True
            ])
            if signals_passed == 3:
                flag = "✅ worth a manual look (3/3 partial signals)"
            elif signals_passed == 2:
                flag = "🟡 maybe (2/3 partial signals)"
            else:
                flag = "⚪ low partial signal, check manually if interested"

            print(f"🔥 NEW PROGRAM: {name} (id: {program_id}, state: {state}) -- {flag}")
            print(f"    -> https://hackerone.com/{handle}")

    if not found_new:
        print(f"[{datetime.now(timezone.utc)}] No new programs. "
              f"Tracking {len(new_seen)} total.")

    return new_seen


def main():
    seen_programs = load_seen_programs()
    print(f"Starting monitor. Tracking {len(seen_programs)} known programs.")

    while True:
        seen_programs = check_new_programs(seen_programs)
        save_seen_programs(seen_programs)
        print(f"[{datetime.now(timezone.utc)}] Check complete. "
              f"Sleeping {POLL_INTERVAL_SECONDS}s.\n")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Berghain Solver for Berghain Bouncer Challenge
# https://berghain.challenges.listenlabs.ai/
# Berghain Challenge - Scenario 1: Constraint Helper Admission Agent

import argparse, os, sys, time, urllib.parse
from collections import Counter
import requests

# -------------- Configurable Parameters --------------
REQUEST_TIMEOUT = (5, 30)
USER_AGENT = "HelperOnlyAgent-S1"
LOG_EVERY = 100
BASE_THROTTLE = 0.01
MAX_RETRIES = 5
BACKOFF_BASE = 0.2
MAX_BACKOFF = 1.0

# -------------- Utility Functions --------------
def url(base, path, **qs):
    return f"{base}{path}" + (f"?{urllib.parse.urlencode(qs)}" if qs else "")

def jitter():
    return 0.5 + 0.5 * (os.urandom(1)[0] / 255)

def safe_get(sess, u):
    tries = 0
    while True:
        tries += 1
        try:
            r = sess.get(u, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429 and tries < MAX_RETRIES:
                ra = r.headers.get("Retry-After")
                delay = float(ra) if ra and ra.isdigit() else min(MAX_BACKOFF, BACKOFF_BASE * (2 ** (tries - 1))) * jitter()
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r
        except KeyboardInterrupt:
            print("\nInterrupted."); sys.exit(1)
        except requests.exceptions.RequestException:
            if tries >= MAX_RETRIES:
                raise
            time.sleep(min(MAX_BACKOFF, BACKOFF_BASE * (2 ** (tries - 1))) * jitter())

def get_json(sess, u):
    return safe_get(sess, u).json()

# -------------- Admission Logic --------------
def should_accept(attrs, person_attrs, needs):
    return any(person_attrs.get(a) and needs[a] > 0 for a in attrs)

# -------------- Main Agent Logic --------------
def run_scenario1(base_url, player_id):
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT, "Connection": "close"})

    game = get_json(sess, url(base_url, "/new-game", scenario=1, playerId=player_id))
    game_id = game["gameId"]
    N = int(game.get("targetAdmissions") or 1000)
    constraints = {c["attribute"]: int(c["minCount"]) for c in game["constraints"]}

    need_rem = dict(constraints)
    admit_true = Counter()
    attrs = list(need_rem.keys())

    resp = get_json(sess, url(base_url, "/decide-and-next", gameId=game_id, personIndex=0))
    if resp.get("status") != "running":
        print("Failed to start:", resp); return

    print(f"Started Scenario 1: N={N}, constraints={constraints}")
    processed = admitted = 0
    last_log = 0
    reasons = Counter()

    while resp.get("status") == "running":
        nxt = resp["nextPerson"]
        idx = nxt["personIndex"]
        A = nxt["attributes"]
        processed += 1

        slots_left = N - admitted
        needs_now = {a: max(0, need_rem[a]) for a in attrs}

        if sum(needs_now.values()) <= 0:
            accept, reason = True, "fill_remaining"
        else:
            accept = should_accept(attrs, A, needs_now)
            reason = "helps_constraints" if accept else "neutral_block"

        time.sleep(BASE_THROTTLE)
        resp = get_json(sess, url(base_url, "/decide-and-next", gameId=game_id, personIndex=idx, accept=str(accept).lower()))
        reasons[reason] += 1

        if accept:
            admitted += 1
            for a in attrs:
                if A.get(a):
                    admit_true[a] += 1
                    if need_rem[a] > 0:
                        need_rem[a] -= 1

        if processed - last_log >= LOG_EVERY or processed < 50 and processed % 10 == 0:
            last_log = processed
            eff = admitted / processed if processed else 0
            print(f"[{processed}] admit={admitted}/{N} eff={eff:.2f} slots_left={slots_left}")
            print(f"  Needs: {need_rem}, Reasons: {dict(reasons)}")

    final = resp.get("status", "stopped").upper()
    print(f"\n=== {final} ===")
    if final == "COMPLETED":
        print("Rejected:", resp.get("rejectedCount"))
        print("Final admits per attribute:", dict(admit_true))
    else:
        print("Reason:", resp.get("reason"))

# -------------- CLI Entry Point --------------
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Scenario 1 Agent — helper-only version")
    p.add_argument("--player-id", required=True)
    p.add_argument("--base-url", required=True)
    args = p.parse_args()
    run_scenario1(args.base_url.rstrip("/"), args.player_id)

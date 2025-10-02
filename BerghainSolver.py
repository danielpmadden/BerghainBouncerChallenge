#!/usr/bin/env python3
# Berghain Solver for Berghain Bouncer Challenge

# https://berghain.challenges.listenlabs.ai/

# Berghain Challenge
# You're the bouncer at a night club. Your goal is to fill the venue with N=1000 people while satisfying constraints like "at least 40% Berlin locals", or "at least 80% wearing all black". People arrive one by one, and you must immediately decide whether to let them in or turn them away. Your challenge is to fill the venue with as few rejections as possible while meeting all minimum requirements.

import os, sys, time, urllib.parse, requests
from collections import Counter, defaultdict

REQUEST_TIMEOUT = (5, 30)
UA = "BerghainBot/v6-trajectory+risk"
LOG_EVERY = 100
BASE_THROTTLE = 0.01  # small sleep to play nice with the API

def url(base, path, **qs):
    return f"{base}{path}" + (f"?{urllib.parse.urlencode(qs)}" if qs else "")

def safe_get(sess, u):
    tries = 0
    while True:
        tries += 1
        try:
            return sess.get(u, timeout=REQUEST_TIMEOUT)
        except KeyboardInterrupt:
            print("\nInterrupted by user."); sys.exit(1)
        except Exception:
            if tries >= 6:
                raise
            time.sleep(min(1.5, 0.2 * (2 ** (tries - 1))))

def get_json(sess, u):
    r = safe_get(sess, u)
    return r.json()

def run_game(scenario: int, base_url: str, player_id: str):
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Connection": "close"})

    # --- Start game ---
    game = get_json(sess, url(base_url, "/new-game", scenario=scenario, playerId=player_id))
    game_id = game["gameId"]
    N = int(game.get("targetAdmissions") or 1000)
    constraints_list = game["constraints"]
    rel_f = (game.get("attributeStatistics") or {}).get("relativeFrequencies", {})

    # Original needed counts per attribute
    need_orig = {c["attribute"]: int(c["minCount"]) for c in constraints_list}
    # Remaining deficits (mutable)
    need_rem = dict(need_orig)
    attrs = list(need_orig.keys())

    # --- State trackers ---
    processed = 0
    admitted = 0

    # How many arrivals had each attr = True (opportunities)
    seen_true = Counter()
    # How many admits contributed to each attr
    admit_true = Counter()

    reasons = Counter()

    # Rarity: a trait is rare if required rate >= 90% of expected base rate,
    # or if base rate itself is <= 10%.
    rare_traits = set()
    for a in attrs:
        p = float(rel_f.get(a, 0.0) or 0.0)
        if p <= 0.10:
            rare_traits.add(a)
        else:
            req_rate = need_orig[a] / N
            if p > 0.0 and req_rate >= 0.9 * p:
                rare_traits.add(a)

    # helper: compute projected risk deltas for remaining needs
    def projected_deltas(slots_left: int):
        # Δ[a] = (observed_true[a] + slots_left * p_a) - need_rem[a]
        # negative => projected underfill
        deltas = {}
        for a in attrs:
            p = float(rel_f.get(a, 0.0) or 0.0)
            deltas[a] = seen_true[a] + slots_left * p - need_rem[a]
        return deltas

    # helper: accept if person helps enough under-pressure traits
    def multi_trait_hits(attr_dict):
        return [a for a in attrs if attr_dict.get(a) and need_rem[a] > 0]

    # First pull
    resp = get_json(sess, url(base_url, "/decide-and-next", gameId=game_id, personIndex=0))
    if resp.get("status") != "running":
        print("Unexpected start:", resp); return

    print(f"v6 running — scenario={scenario} | N={N} | attrs={len(attrs)}")
    last_log = 0
    t0 = time.time()

    while resp.get("status") == "running":
        nxt = resp["nextPerson"]
        idx = nxt["personIndex"]
        A = nxt["attributes"]

        processed += 1
        # Update observed opportunities
        for a in attrs:
            if A.get(a, False):
                seen_true[a] += 1

        # Remaining slots if we accept this person now:
        slots_left_now = N - admitted

        # Short-circuit: if all constraints satisfied, greedily fill
        if sum(need_rem.values()) <= 0:
            accept, reason = True, "fill_after_constraints"
        else:
            # Compute hits & multi-hit count
            hits = multi_trait_hits(A)
            k_hits = len(hits)

            # Projected deltas BEFORE deciding on this person
            deltas = projected_deltas(slots_left_now)

            # Identify at-risk attributes (projected underfill)
            # Use a tolerance buffer so we react early enough.
            AT_RISK = [a for a in attrs if deltas[a] < -5]

            # Overfill guard per attribute: if we've already admitted >= 102% of need_orig[a]
            # (only active while not all constraints met)
            overfilled_hit = any(admit_true[a] >= 1.02 * need_orig[a] for a in hits if need_orig[a] > 0)

            # Trajectory budgeting:
            # Among the opportunities seen for attribute a, what fraction have we admitted?
            # Target fraction ~ need_orig[a]/(expected total with attr true) ≈ need_orig[a]/(N* p_a)
            # We compare admitted/seen to this target to avoid falling behind.
            budget_rescue = False
            for a in hits:
                seen = max(1, seen_true[a])    # avoid div-by-zero
                admitted_for_a = admit_true[a]
                observed_admit_ratio = admitted_for_a / seen
                p = float(rel_f.get(a, 0.0) or 0.0)
                expected_total = max(1.0, N * p)  # expected with attr true
                target_ratio = need_orig[a] / expected_total
                # Rescue if we're below 90% of the required trajectory and still have need remaining
                if need_rem[a] > 0 and observed_admit_ratio < 0.90 * target_ratio:
                    budget_rescue = True
                    break

            # Rarity boost if person has any rare trait still needed
            rare_boost = any((a in rare_traits) and (need_rem[a] > 0) and A.get(a, False) for a in attrs)

            # Decision policy (ordered):
            if AT_RISK and not any(A.get(a, False) for a in AT_RISK):
                accept, reason = False, "risk_block"  # doesn't help what's most endangered
            elif overfilled_hit:
                accept, reason = False, "overfill_guard"  # prevents hogging by easy traits
            elif k_hits >= 2:
                accept, reason = True, "multi_trait_boost"
            elif budget_rescue:
                accept, reason = True, "budget_rescue"
            elif rare_boost and k_hits >= 1:
                accept, reason = True, "rare_trait_boost"
            elif k_hits >= 1:
                accept, reason = True, "standard_help"
            else:
                accept, reason = False, "no_help"

        # Send decision
        time.sleep(BASE_THROTTLE)
        resp = get_json(sess, url(base_url, "/decide-and-next",
                                  gameId=game_id, personIndex=idx, accept=str(accept).lower()))
        reasons[reason] += 1

        if accept:
            admitted += 1
            # Update remaining needs & admit counters
            for a in attrs:
                if need_rem[a] > 0 and A.get(a, False):
                    need_rem[a] -= 1
                    if need_rem[a] < 0: need_rem[a] = 0
                    admit_true[a] += 1

        # Logging
        if processed - last_log >= LOG_EVERY or (processed < 50 and processed % 10 == 0):
            last_log = processed
            eff = (admitted / processed) if processed else 0.0
            total_need = sum(need_rem.values())
            # show top deficits
            top_def = sorted(need_rem.items(), key=lambda kv: kv[1], reverse=True)[:3]
            # show quick deltas snapshot
            slots_left = max(0, N - admitted)
            deltas_now = projected_deltas(slots_left)
            at_risk_view = {a: round(deltas_now[a], 1) for a in attrs if deltas_now[a] < -5}
            # fill ratios vs target
            fr_line = {}
            for a in attrs:
                seen = max(1, seen_true[a])
                p = float(rel_f.get(a, 0.0) or 0.0)
                expected_total = max(1.0, N * p)
                target_ratio = need_orig[a] / expected_total
                fr_line[a] = f"{(admit_true[a]/seen):.2%}/{target_ratio:.2%}"
            print(f"[{processed}] admit={admitted}/{N} eff={eff:.2f} rem_need={total_need}")
            print("  top_deficits:", top_def)
            if at_risk_view:
                print("  projected_underfill Δ:", at_risk_view)
            print("  fill_ratio(obs/target):", fr_line)
            print("  reasons:", dict(reasons))

    # Completed / failed
    status = resp.get("status")
    if status == "completed":
        print("\n=== COMPLETED ===")
        print("Rejected:", resp.get("rejectedCount"))
    elif status == "failed":
        print("\n=== FAILED ===")
        print("Reason:", resp.get("reason"))
    else:
        print("\n=== STOP ===")
        print(resp)

# -------- CLI --------
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Berghain v6 — trajectory-aware admissions")
    p.add_argument("--scenario", type=int, required=True)
    p.add_argument("--player-id", type=str, required=True)
    p.add_argument("--base-url", type=str, required=True)
    args = p.parse_args()
    run_game(args.scenario, args.base_url.rstrip("/"), args.player_id)

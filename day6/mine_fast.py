#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mine_nice_fast.py
Boost balance by mining blocks with nice=<who> safely under heavy head churn.
- Uses txpool head hash as prev_hash.
- Re-checks head DURING PoW (every 512 nonces) and restarts if it changes.
- Only sets nice=<who> when the txpool snapshot contains NO tx touching <who>
  (neither src==who nor dst==who).
- Mines EMPTY blocks when setting nice to avoid accidental gifts to <who>.

Usage:
  python3 mine_nice_fast.py --who hacker --target 10

Env:
  NORTH_POOLE (default: http://localhost)
"""
import os, json, time, hashlib, argparse, requests

NORTH_POOLE = os.environ.get("NORTH_POOLE", "http://localhost")
DIFFICULTY = 16
DIFFICULTY_PREFIX = "0" * (DIFFICULTY // 4)
RECHECK_INTERVAL = 512

# ---- HTTP helpers ----
def http_get(path: str, **kwargs):
    url = f"{NORTH_POOLE}{path}"
    r = requests.get(url, timeout=kwargs.pop("timeout", 5), **kwargs)
    r.raise_for_status()
    return r

def http_post(path: str, json_body: dict, **kwargs):
    url = f"{NORTH_POOLE}{path}"
    r = requests.post(url, json=json_body, timeout=kwargs.pop("timeout", 5), **kwargs)
    return r

# ---- Chain helpers ----
def hash_block(block: dict) -> str:
    block_str = json.dumps(block, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(block_str.encode()).hexdigest()

def get_head():
    j = http_get("/block").json()
    return j["hash"], j["block"]

def get_chain_from_head() -> list:
    head_hash, head_block = get_head()
    chain = [head_block]
    current_hash = head_block.get("prev_hash")
    while current_hash:
        try:
            r = http_get("/block", params={"hash": current_hash})
        except Exception:
            break
        j = r.json()
        blk = j.get("block")
        if not blk:
            break
        chain.append(blk)
        current_hash = blk.get("prev_hash")
    chain.reverse()
    return chain

def get_txpool():
    j = http_get("/txpool").json()
    return j.get("hash"), j.get("txs", [])


def count_nice(chain=None, who="hacker") -> int:
    if chain is None:
        chain = get_chain_from_head()
    return sum(1 for blk in chain if blk.get("nice") == who)


def mine_empty_with_nice(who: str) -> bool:
    """Mine one EMPTY block with nice=<who>, with mid-PoW head rechecks."""
    while True:
        head_hash, txs = get_txpool()
        # Ensure snapshot has no tx touching 'who'
        touches_who = any((tx.get("src") == who) or (tx.get("dst") == who) for tx in txs)
        if touches_who:
            # Wait briefly for a clean snapshot
            time.sleep(0.1)
            continue
        # Parent index
        r = http_get("/block", params={"hash": head_hash})
        parent_index = r.json()["block"]["index"]
        block = {
            "index": parent_index + 1,
            "prev_hash": head_hash,
            "nonce": 0,
            "txs": [],
            "nice": who,
        }
        nonce = 0
        base_head = head_hash
        while True:
            block["nonce"] = nonce
            h = hash_block(block)
            if h.startswith(DIFFICULTY_PREFIX):
                break
            nonce += 1
            if nonce % RECHECK_INTERVAL == 0:
                latest_head, _ = get_txpool()
                if latest_head != base_head:
                    # Head changed; restart on new head
                    break
        latest_head, _ = get_txpool()
        if latest_head != base_head or not h.startswith(DIFFICULTY_PREFIX):
            continue
        resp = http_post("/block", json_body=block)
        if resp.status_code == 200:
            return True
        time.sleep(0.05)


def mine_nice_fast(target: int, who: str):
    chain = get_chain_from_head()
    cur = count_nice(chain, who=who)
    print(f"[nice-fast] current nice({who})={cur}; target={target}")
    while cur < target:
        ok = mine_empty_with_nice(who)
        if ok:
            chain = get_chain_from_head()
            cur = count_nice(chain, who=who)
            print(f"[nice-fast] accepted empty block; nice({who}) count now {cur}")
        else:
            print("[nice-fast] rejected; retrying...")
    print(f"[nice-fast] target reached: nice({who})={cur}")


def main():
    ap = argparse.ArgumentParser(description="Safely increase nice(<who>) with mid-PoW head checks")
    ap.add_argument("--who", type=str, default="hacker", help="Identity to mark as nice")
    ap.add_argument("--target", type=int, default=10, help="Target nice count (cap ~10)")
    args = ap.parse_args()
    mine_nice_fast(target=args.target, who=args.who)

if __name__ == 

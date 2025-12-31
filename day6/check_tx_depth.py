#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_tx_depth.py
Given a transaction nonce (e.g., your final letter's nonce), report:
 - Whether it is mined (present inside any block on chain)
 - The block index that contains it
 - The current head index
 - The confirmation depth (head_index - tx_block_index)

Usage:
  python3 check_tx_depth.py --nonce 7a4fd92a-0263-40dd-bc11-7e189ecf2c8f

Env:
  NORTH_POOLE (default: http://localhost)
"""
import os, json, argparse
import requests

NORTH_POOLE = os.environ.get("NORTH_POOLE", "http://localhost")

def http_get(path: str, **kwargs):
    url = f"{NORTH_POOLE}{path}"
    r = requests.get(url, timeout=kwargs.pop("timeout", 5), **kwargs)
    r.raise_for_status()
    return r

def get_head():
    j = http_get("/block").json()
    return j["hash"], j["block"]

def get_chain_from_head():
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

def main():
    ap = argparse.ArgumentParser(description="Check mined depth of a tx by nonce")
    ap.add_argument("--nonce", required=True, help="Transaction nonce to search for")
    args = ap.parse_args()

    _, head = get_head()
    head_index = head["index"]

    chain = get_chain_from_head()
    tx_block_index = None
    for blk in chain:
        for tx in blk.get("txs", []):
            if tx.get("nonce") == args.nonce:
                tx_block_index = blk["index"]
                break
        if tx_block_index is not None:
            break

    if tx_block_index is None:
        print(f"nonce={args.nonce} not found in mined blocks (may still be queued/expired)")
        return

    depth = head_index - tx_block_index
    print(f"nonce={args.nonce}\n  mined_in_block_index={tx_block_index}\n  head_index={head_index}\n  confirmations={depth}")

if __name__ == "__main__":
    main()

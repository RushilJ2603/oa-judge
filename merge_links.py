#!/usr/bin/env python3
"""Merge _research/links.json (from the research agent) into each problem.json `links` field.

Kept separate from problem.json authoring so the research agent never has to touch problem.json
(avoids write conflicts with the packaging agents). Run once, after both land.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
LINKS = os.path.join(ROOT, "_research", "links.json")
PROBLEMS = os.path.join(ROOT, "problems")


def main():
    if not os.path.exists(LINKS):
        raise SystemExit(f"no {LINKS} — research agent has not produced it yet")
    data = json.load(open(LINKS))
    merged = 0
    for pid, links in data.items():
        pj = os.path.join(PROBLEMS, pid, "problem.json")
        if not os.path.exists(pj):
            print(f"  skip {pid}: no problem.json")
            continue
        meta = json.load(open(pj))
        meta["links"] = links
        json.dump(meta, open(pj, "w"), indent=2)
        merged += 1
        print(f"  {pid}: {len(links)} link(s)")
    print(f"merged links into {merged} problems")


if __name__ == "__main__":
    main()

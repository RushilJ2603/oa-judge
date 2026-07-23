#!/usr/bin/env python3
"""Random input for Uber Q1 (min penalty partition). Line: "s D Seg".
argv[1]=seed, argv[2]=integer size hint (caps string length). Small default; 2-3 letter alphabet so
equal-adjacent runs actually occur. |s| kept modest because the reference is O(n^2)."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(400, max(1, size))
alphabet = "ab" if rng.random() < 0.5 else "abc"
s = "".join(rng.choice(alphabet) for _ in range(n))
D = rng.randint(0, 10 if size <= 20 else 10**9)
Seg = rng.randint(0, 20 if size <= 20 else 10**9)
print(f"{s} {D} {Seg}")

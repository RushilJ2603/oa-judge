#!/usr/bin/env python3
"""Random input generator for Millennium Q1."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(100000, max(1, size * 2))
s = "".join(rng.choice(['0', '1']) for _ in range(n))
print(s)

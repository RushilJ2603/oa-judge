#!/usr/bin/env python3
"""Random input generator for Checkerboard Subgrids."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 5
rng = random.Random(seed)

n = min(2000, max(1, size))
m = min(2000, max(1, size))

print(f"{n} {m}")
for _ in range(n):
    row = "".join(rng.choice(['0', '1']) for _ in range(m))
    print(row)

#!/usr/bin/env python3
"""Random input for Uber Q2 (bundling target). Line 1: n. Line 2: n distinct ints in 1..2n.
argv[1]=seed, argv[2]=integer size hint (caps n). Small default so stress shrinks fast."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(100000, max(1, size))
T = rng.sample(range(1, 2 * n + 1), n)
print(n)
print(" ".join(map(str, T)))

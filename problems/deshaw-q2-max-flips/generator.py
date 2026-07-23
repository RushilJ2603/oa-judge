#!/usr/bin/env python3
"""Random input generator for Max Flips."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(200000, max(1, size))
a = [rng.randint(1, max(10, size * 2)) for _ in range(n)]

print(n)
print(" ".join(map(str, a)))

#!/usr/bin/env python3
"""Random input generator for Music Player."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(200000, max(2, size))
q = min(200000, max(1, size))

print(f"{n} {q}")
a = list(range(1, n + 1))
rng.shuffle(a)
print(" ".join(map(str, a)))

for _ in range(q):
    if rng.random() < 0.5:
        # Move query
        u = rng.randint(1, n)
        v = rng.randint(1, n)
        while v == u:
            v = rng.randint(1, n)
        print(f"1 {u} {v}")
    else:
        # Positional query
        k = rng.randint(1, n)
        print(f"2 {k}")

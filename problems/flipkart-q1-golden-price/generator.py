#!/usr/bin/env python3
"""Random input generator for Golden Price.

Prints one line "X Y" with 1 < X, Y < 100000. argv[1]=seed, argv[2]=size hint (bounds the range
width so stress cases stay small and shrinkable).
"""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

# size scales the window width: small sizes => tiny ranges => readable counterexamples.
width = min(99997, max(1, size * size))
x = rng.randint(2, 99999)
y = min(99999, x + rng.randint(0, width))
if rng.random() < 0.5:
    x, y = y, x                      # exercise the unordered-range path
print(f"{x} {y}")

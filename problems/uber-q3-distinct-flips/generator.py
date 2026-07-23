#!/usr/bin/env python3
"""Random input for Uber Q3 (distinct flips). One binary string.
argv[1]=seed, argv[2]=integer size hint (caps the length). Small default so stress shrinks fast."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(100000, max(1, size))
print("".join(rng.choice("01") for _ in range(n)))

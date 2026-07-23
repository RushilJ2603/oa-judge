#!/usr/bin/env python3
"""Random input generator for Millennium Q2."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

n = min(100000, max(2, size))

edges = set()
# Make a connected path first to ensure connected-ish graph
for i in range(1, n):
    u = rng.randint(0, i - 1)
    v = i
    edges.add((u, v))

extra_edges = min(200000 - n + 1, rng.randint(0, size))
for _ in range(extra_edges):
    u = rng.randint(0, n - 1)
    v = rng.randint(0, n - 1)
    if u != v:
        if u > v:
            u, v = v, u
        edges.add((u, v))

m = len(edges)

start = rng.randint(0, n - 1)
end_node = rng.randint(0, n - 1)
k = min(15, rng.randint(0, min(n, size)))

tasks_pool = list(range(n))
rng.shuffle(tasks_pool)
tasks = tasks_pool[:k]

print(f"{n} {m}")
for u, v in edges:
    print(f"{u} {v}")
print(f"{start} {end_node} {k}")
if k > 0:
    print(" ".join(map(str, tasks)))
else:
    print("")

#!/usr/bin/env python3
"""Random input generator for Marathon Checkpoints."""

import sys
import random

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    rng = random.Random(seed)
    
    # size scales the max number of nodes, small by default
    n_max = min(100, max(3, size))
    n = rng.randint(3, n_max)
    
    checkpoints = set()
    root_val = rng.randint(1, 1000)
    checkpoints.add(root_val)
    
    paths = [""]
    valid_nodes = []
    
    for _ in range(n - 1):
        while True:
            parent_path = rng.choice(paths)
            dir_c = rng.choice(["L", "R"])
            new_path = parent_path + dir_c
            if new_path not in paths:
                paths.append(new_path)
                val = rng.randint(1, 1000)
                while val in checkpoints:
                    val = rng.randint(1, 1000)
                checkpoints.add(val)
                valid_nodes.append((new_path, val))
                break
                
    print(n)
    print(root_val)
    for p, v in valid_nodes:
        print(f"{p} {v}")

if __name__ == "__main__":
    main()

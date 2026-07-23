# Editorial

Because revisiting nodes is allowed, the walk imposes no constraint linking one leg to the next. You may re-enter any node freely. A walk visiting the tasks in a given order has a length equal to the sum of the shortest-path distances between consecutive milestones (the tasks, plus the start and end nodes).

The problem collapses to finding the minimum over all orderings of the tasks of the sum of pairwise shortest paths from start, through the tasks in that order, to end.

1. **BFS from each of the `k+2` milestone nodes**: This gives the dense distance matrix.
2. **Bitmask DP**: Compute `dp[mask][i]` which equals the shortest walk from start that has covered the task set `mask` and currently stands on task `i`.

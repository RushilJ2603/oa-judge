# Shortest Walk Visiting All Task Nodes

You are given an undirected, unweighted graph with `n` nodes and `m` edges (every edge has weight 1). You are given a **start** node, an **end** node, and a set of `k` **task** nodes.

Find the length of the shortest **walk** that begins at start, ends at end, and passes through every task node at least once. Nodes and edges may be reused any number of times. Print `-1` if no such walk exists.

## Input

```
n m
m lines: u v            (an undirected edge)
start end k
k node ids              (the task nodes; omitted/blank line when k = 0)
```

## Output

A single integer: the length of the shortest such walk, or `-1`.

## Constraints

```
2 <= n <= 100000
1 <= m <= 200000
0 <= k <= 15
nodes are 0-indexed
```

## Example 1

Input:
```
6 6
0 1
1 2
2 3
1 4
4 5
5 3
0 3 2
2 4
```
Output:
```
5
```

The optimum is `0 → 1 → 4 → 1 → 2 → 3`: length **5**. Note that it **revisits node 1** — the detour to task node 4 is made by going out and coming straight back.

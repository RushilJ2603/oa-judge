The numbers `1, 2, ..., 2n` are to be partitioned into `n` unordered **bundles** of two numbers each.
From each bundle you take either its **minimum** or its **maximum**. You are given a **target** array
`T` of `n` distinct values drawn from `1...2n`; the multiset of taken values must equal `T`.

For each `x` in `{0, 1, ..., n}`, decide whether the target can be produced while taking the **min** from
**exactly `x`** bundles (and the max from the other `n - x`). Report the set of feasible `x`.
The feasible `x` will always form a contiguous range `[xmin, xmax]`.

**Input**
The first line contains an integer `n`.
The second line contains `n` space-separated distinct integers `T[0], T[1], ..., T[n-1]` representing the target array.

**Output**
Two space-separated integers: `xmin` and `xmax`, the inclusive range of feasible min-pick counts.

**Constraints**
- `1 <= n <= 10^5`
- The target array contains `n` distinct integers, each in the range `[1, 2n]`

**Example**
Input:
```
3
1 3 5
```
Output:
```
1 3
```

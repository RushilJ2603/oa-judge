# Music Player

You are building the queue for a music player. The playlist is a sequence of `n` **distinct** track IDs, initially given as a shuffled permutation of `1 … n`. Positions in the playlist are 1-indexed.

Process `q` queries of two kinds:

- `1 u v` — **Move.** Remove track `u` from its current position and re-insert it immediately **before** track `v`. It is guaranteed that `u ≠ v` and both are present in the playlist.
- `2 k` — **Query.** Print the track ID currently at position `k` (1-indexed).

## Input

The first line contains two integers `n` and `q`.
The second line contains `n` integers `a_1, a_2, ..., a_n` representing the initial playlist (a permutation of 1 to n).
The next `q` lines each contain a query: either `1 u v` or `2 k`.

## Output

For each type-2 query, print one line containing the track ID at position `k`.

## Constraints

```
1 <= n, q <= 200000
1 <= a_i, u, v <= n
All a_i are distinct
1 <= k <= n
```

## Example 1

Input:
```
5 4
3 1 4 5 2
2 3
1 4 1
2 1
2 2
```
Output:
```
4
3
4
```
Walkthrough: start `[3,1,4,5,2]`. Query `2 3` → position 3 holds `4`. Move `1 4 1`: pull `4` out and put it immediately before `1` → `[3,4,1,5,2]`. Query `2 1` → `3`. Query `2 2` → `4`.

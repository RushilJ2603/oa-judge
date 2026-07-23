# Checkerboard Subgrids

Given an `n × m` binary grid, count the number of **axis-aligned rectangular subgrids** that form a valid checkerboard — that is, subgrids in which every pair of orthogonally adjacent cells (up, down, left, right) holds **different** values.

Subgrids are identified by their position, so two subgrids at different locations count separately even if their contents are identical. A single cell is a valid subgrid (it has no adjacent pairs inside it, so the condition holds vacuously).

## Input

The first line contains two integers `n` and `m`.
The next `n` lines each contain a string of `m` characters, where each character is either '0' or '1'.

## Output

A single integer: the number of checkerboard subgrids.

## Constraints

```
1 <= n, m <= 2000
```

## Example 1

Input:
```
2 2
01
10
```
Output:
```
9
```
The grid is a perfect checkerboard. It has four 1×1 subgrids, two 1×2 subgrids, two 2×1 subgrids, and one 2×2 subgrid, giving a total of 9 valid checkerboard subgrids.

## Example 2

Input:
```
3 3
101
010
101
```
Output:
```
36
```
The grid is a 3×3 perfect checkerboard. Every rectangular subgrid is valid, yielding 36 subgrids in total.

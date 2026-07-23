# Max Flips

You are given an array `a` of `n` **positive** integers. You may choose any subset of positions and flip the sign of each chosen element (`a_i → -a_i`). A choice is **valid** if after flipping, every prefix sum is strictly positive:

```
for every i in 1..n:   a_1 + a_2 + … + a_i  >  0
```

Return the **maximum number of elements** that can be flipped over all valid choices.

## Input

The first line contains an integer `n`.
The second line contains `n` positive integers `a_1, a_2, ..., a_n`.

## Output

A single integer: the maximum count of flipped elements.

## Constraints

```
1 <= n <= 200000
1 <= a_i <= 10^9
```

## Example 1

Input:
```
5
4 1 2 1 3
```
Output:
```
3
```
One optimal choice: flip `a_2`, `a_4` and `a_5`, giving `4, -1, 2, -1, -3` with prefix sums `4, 3, 5, 4, 1` — all strictly positive, 3 flips.

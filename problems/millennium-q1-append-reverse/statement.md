# Append and Reverse

You are given a binary string `s` of length `n`. The following process defines a string `b`:

```
b := ""                      (empty)
for i = 0 to n-1:
    b := b + s[i]            (append s[i] at the end of b)
    b := reverse(b)          (then reverse the whole of b)
```

You may **rearrange the characters of `s` arbitrarily** before the process runs — that is, replace `s` by any permutation of its own characters. The multiset of characters is fixed; only their order may change.

Find a rearrangement of `s` that makes the final `b` **lexicographically maximum**.

## Input

A single line containing the binary string `s`.

## Output

A single line containing the unique rearranged string `s` that maximizes the final `b`. (Note: output ONLY the rearranged string `s`, not `b`).

## Constraints

```
1 <= n <= 100000
s consists only of the characters '0' and '1'
```

## Example 1

Input:
```
0110
```
Output:
```
0101
```
Trace the process on the rearranged `0101`:
- i=0: append `0`, b=`0`, reverse b=`0`
- i=1: append `1`, b=`01`, reverse b=`10`
- i=2: append `0`, b=`100`, reverse b=`001`
- i=3: append `1`, b=`0011`, reverse b=`1100`

Final `b = 1100`, which is the largest arrangement of two 1s and two 0s.

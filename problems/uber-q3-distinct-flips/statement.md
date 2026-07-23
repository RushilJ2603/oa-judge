You are given a binary string `s`. You may choose one contiguous substring and **flip** it (complement
every bit: `0` to `1` and `1` to `0`) **at most once**. 

How many distinct strings can result (counting `s` itself, the result of flipping nothing)?

**Input**
A single line containing the binary string `s`.

**Output**
A single integer: the number of distinct strings that can be formed.

**Constraints**
- `1 <= |s| <= 10^6`

**Example**
Input:
```
0110
```
Output:
```
11
```

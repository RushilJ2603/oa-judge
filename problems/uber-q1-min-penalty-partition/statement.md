You are given a string `s`, an integer `duplicatePenalty` `D`, and an integer `segmentPenalty` `Seg`.
You may cut `s` into contiguous segments; **each cut costs `Seg`**. Within a segment, adjacent equal
characters incur a `duplicatePenalty`. Splitting between two equal characters separates them, so they
no longer share a segment and no longer incur that penalty. Minimise the total penalty.

**Specifically**, the rule is applied per-element: within a segment, a run of `k` (where `k >= 2`)
equal characters costs `k * D`. A run of length 1 costs nothing.

**Input**
A single line containing the string `s`, the integer `D`, and the integer `Seg` separated by spaces.

**Output**
A single integer: the minimum achievable total penalty.

**Constraints**
- `1 <= |s| <= 10^5`
- `0 <= D, Seg <= 10^9`

**Example 1**
Input:
```
aab 5 3
```
Output:
```
3
```
Explanation:
Keep `aab` whole, the run `aa` costs `2 * 5 = 10`.
Cut to `a|ab`, the cut costs `Seg = 3`. The runs `a` and `ab` cost 0.
The minimum total penalty is 3.

**Example 2**
Input:
```
aaaa 1 10
```
Output:
```
4
```
Explanation:
Keep `aaaa` whole, the run `aaaa` costs `4 * 1 = 4`.
Any cut would cost at least `Seg = 10`.
The minimum total penalty is 4.

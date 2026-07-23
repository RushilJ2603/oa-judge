# Golden Price — editorial

**Parse the definition first.** "The difference between the sum of all the digits and the highest
digit is equal to the highest digit" means `digitSum(G) − maxDigit(G) == maxDigit(G)`, i.e.
`digitSum(G) == 2 × maxDigit(G)`. Verify against the given examples before coding: 352 → 10 = 2·5 ✓;
32812 → 16 = 2·8 ✓.

With `X, Y < 100000` the range has at most 10⁵ numbers of ≤ 6 digits, so a straight scan is ~6·10⁵
digit operations — instant. No cleverness needed.

Two decisions that prevent hidden-test failures:

- **Swap if `X > Y`.** The statement never promises `X < Y`. One line removes a whole class of
  failure.
- **Accumulate in `long long`.** The signature returns `int`, but the running sum over the range can
  reach ~5·10⁸ — close enough to the `int` ceiling to be worth removing from consideration entirely.

Complexity: O((Y−X)·d) time, O(1) space, d ≤ 6.

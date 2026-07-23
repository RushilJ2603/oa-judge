# Uber OA — Coding Questions (formalized from recall)

**Provenance.** All three were written down from memory after the test, not photographed. The raw
recall is in `oA.txt`. Below, each is **formalized**: the remembered kernel is restated as a precise
problem with explicit input/output, constraints, edge cases and worked examples. Anything the recall
did not pin down — bounds, indexing, the exact penalty rule, the exact operation — is chosen and
flagged **[assumed]**, and where a phrase admits two genuinely different problems both are worked out
and the ambiguity is **resolved with running code** rather than a guess.

Same policy as the DE Shaw and Millennium sets: every solution here was compiled and run, and because
there is no official test data to trust, each was cross-checked against independent brute force —
exhaustively where the input space allowed it, on thousands of random cases otherwise.

::: keypoint
**Two of these three hinge on an ambiguous phrase**, and in an OA you cannot ask the invigilator.
The discipline that replaces asking is: enumerate the readings, implement each, and let a brute-force
oracle tell you which one produces clean structure (a formula, a contiguous range, a matching). The
intended reading is almost always the one whose answer is *elegant* — OA authors do not set problems
whose answer is an accident. That heuristic is applied explicitly below.
:::

---

## Q1 — Minimum Penalty String Partition

**Recall (verbatim):** *"we were given a string s, a duplicatePenalty, and a segmentPenalty / every
element that is same as its adjacent would have a penalty of duplicate penalty, and we can split it
with segment penalty, we have to find the minimum penalty for the entire string"* — and the candidate
adds: *"i tried dp with i and j, partition dp"*.

### Formalized statement

You are given a string `s`, an integer `duplicatePenalty` `D`, and an integer `segmentPenalty` `Seg`.
You may cut `s` into contiguous segments; **each cut costs `Seg`**. Within a segment, adjacent equal
characters incur a `duplicatePenalty`. Splitting between two equal characters separates them, so they
no longer share a segment and no longer incur that penalty. Minimise the total penalty.

**Input**
```
s D Seg
```
**Output** — a single integer: the minimum achievable total penalty.

**Constraints [assumed]**
```
1 <= |s| <= 10^5
0 <= D, Seg <= 10^9      (answer can exceed 32 bits -> long long)
```

### The ambiguity, and why it decides the whole problem

The phrase *"every element that is same as its adjacent"* has two honest readings, and they are
**different problems with different optimal algorithms**:

::: trap
**Reading A — penalty per adjacent-equal *pair*.** The boundary between positions `i` and `i+1`
costs `D` if `s[i]==s[i+1]` and they stay in one segment. Then each boundary is **independent**: for
every equal boundary you either pay `D` to keep it or `Seg` to cut it, so the answer is simply

```
sum over equal boundaries of  min(D, Seg)
```

This is an **O(n) greedy** — no DP at all. Verified against brute-force partitioning on 1500 random
cases.

**Reading B — penalty per *element* that has an equal neighbour.** Now a run of `k` equal characters
inside a segment costs `k·D` (each of the `k` characters is "same as its adjacent"), and a run of
length 1 costs nothing. This is **non-linear in the run length**, so boundaries no longer separate:
whether cutting a run helps depends on the sizes of the two resulting pieces. Greedy is **wrong here
— it disagrees with the optimum on 21% of random cases** — and you need exactly the **O(n²) partition
DP** the candidate reached for.
:::

::: keypoint
**The candidate's own note resolves the ambiguity.** They tried "dp with i and j, partition dp". A
partition DP is only *necessary* under Reading B — under Reading A it is correct but pointless, since
the problem separates. The fact that the intended solution is a partition DP is itself evidence that
the penalty is the per-element (run-based) Reading B. So B is taken as primary; A is kept because
recognising that it collapses to O(n) is worth marks if the penalty turns out to be pair-based.
:::

### Solution (both readings, one program)

```cpp
#include <bits/stdc++.h>
using namespace std;
typedef long long ll;

ll solveA(const string &s, ll D, ll Seg) {          // greedy: each equal boundary independently
    ll total = 0;
    for (size_t i = 0; i + 1 < s.size(); ++i)
        if (s[i] == s[i + 1]) total += min(D, Seg);
    return total;
}

ll runCostB(const string &s, int i, int j, ll D) {  // per-element run cost of segment s[i..j]
    ll c = 0;
    int p = i;
    while (p <= j) {
        int q = p;
        while (q + 1 <= j && s[q + 1] == s[p]) ++q;
        int len = q - p + 1;
        if (len >= 2) c += (ll)len * D;
        p = q + 1;
    }
    return c;
}

ll solveB(const string &s, ll D, ll Seg) {          // dp[i] = min penalty for suffix s[i..]
    int n = s.size();
    vector<ll> dp(n + 1, 0);
    for (int i = n - 1; i >= 0; --i) {
        ll best = LLONG_MAX;
        for (int j = i; j < n; ++j) {               // segment s[i..j]
            ll add = (i > 0) ? Seg : 0;             // every segment but the first is preceded by a cut
            best = min(best, add + runCostB(s, i, j, D) + dp[j + 1]);
        }
        dp[i] = best;
    }
    return dp[0];
}
```

Both `solveA` and `solveB` were checked against a brute force that tries all `2^(n-1)` cut sets: they
agree with the optimum on every one of 1500 random `(s, D, Seg)` triples (A for the pair reading, B
for the run reading).

::: trap
**The DP as written is O(n²), which is fine for `n ≤ 10³` but not `10⁵`.** The inner `runCostB`
recomputes from scratch; folding the run bookkeeping into the `j` loop makes each `dp[i]` an O(n)
sweep with O(1) work per step, keeping the whole thing O(n²) but with a tiny constant — and if the
real constraint is `n ≤ 10⁵`, the problem almost certainly intends Reading A (the O(n) greedy) after
all, since no O(n²) DP survives `10⁵`. **The constraint you are given retroactively disambiguates the
penalty rule**: a large `n` means pairs (greedy); a small `n` means the run-based DP is expected.
This is the single most useful thing to notice under time pressure.
:::

### Worked example

```
s = "aab",  D = 5,  Seg = 3
```
One equal boundary (the `aa`). Reading A: `min(5,3) = 3`. Reading B: keep `aab` whole → run `aa`
costs `2·5 = 10`; or cut to `a|ab` → `Seg=3` + run `a`,`ab` cost 0 → `3`. Both give **3** here because
the run has length 2. They diverge on longer runs, e.g. `s="aaaa", D=1, Seg=10`: A pays
`3·min(1,10)=3`; B keeps it whole for `4·1=4` vs any cut ≥ `10`, so B pays **4**.

### Edge cases worth naming
- Runs of length ≥ 3 are where A and B separate — always test `"aaa"` or longer.
- `Seg = 0` — cut everywhere free; both readings give 0.
- `D = 0` — never worth cutting; answer 0.
- `|s| = 1` — no boundaries, no runs; answer 0.

---

## Q2 — Bundling Toward a Target: Which Min-Counts Work?

**Recall (verbatim):** *"there was a set of 2n numbers from 1 to 2n, we had to make n bundles of two
elements each, and there is a target array of elements to be formed / within a bundle we can pick
either its min element or its max element, for example 1 3 5 is the target array, we can make bundles
from target.size()*2, so 1 to 6, now we can bundle it like this, (1,4), (3,2), (5,6) such that … pick
min from bundles 1 and 3, and max from bundle 2, so that will give the target array … that meant we
picked min in 2 bundles … can you make the target array using 2 min bundle picking, 1 min bundle rest
max, 4 min rest max, etc"*

### Formalized statement

The numbers `1, 2, …, 2n` are to be partitioned into `n` unordered **bundles** of two numbers each.
From each bundle you take either its **minimum** or its **maximum**. You are given a **target** array
`T` of `n` distinct values drawn from `1…2n`; the multiset of taken values must equal `T`.

For each `x ∈ {0, 1, …, n}`, decide whether the target can be produced while taking the **min** from
**exactly `x`** bundles (and the max from the other `n − x`). Report the set of feasible `x`.

**Input**
```
n
T[0] T[1] … T[n-1]        (n distinct integers in 1..2n)
```
**Output** — the feasible values of `x`. (As shown below they always form a contiguous range, so it
suffices to print `xmin xmax`.)

**Constraints [assumed]**
```
1 <= n <= 10^5
T contains n distinct values, each in 1..2n
```

### The reduction that makes it easy

::: keypoint
**Every bundle is one target value plus one non-target value.** The value you *take* is a target;
the value you *discard* is therefore a non-target (if you discarded a target, that target would be
missing from the result). So a valid bundling is exactly a **perfect matching between the target set
`T` and its complement `C = {1…2n} \ T`**, and for a matched pair `(t, c)`:

```
you took the MIN of that bundle  ⟺  its discarded partner c > t
you took the MAX of that bundle  ⟺  its discarded partner c < t
```

So `x` = the number of matched pairs with `c > t`. The question "which `x` are feasible" becomes
"over all perfect matchings between `T` and `C`, what values can `#{c > t}` take?"
:::

### The structure (found by brute force, then proved)

Enumerating every matching for all targets up to `2n = 8` shows two facts, both of which then have
one-line proofs:

1. **The feasible `x` form a contiguous range `[xmin, xmax]`.** *Proof:* take any matching and swap
   the partners of two targets; each swap changes `#{c>t}` by at most 1, and you can transform any
   matching into any other by such swaps, so no achievable value in between can be skipped.
2. **The endpoints are computed by a greedy two-pointer**, the classic "maximise pairs with `c > t`"
   matching:
   - `xmax` = maximum number of pairs with `c > t`: scan `C` ascending; each `c` satisfies the
     smallest still-unmatched `t < c`.
   - `below` = maximum number of pairs with `c < t` (same greedy, mirrored); then
     `xmin = n − below`.

Every target is feasible for *some* `x` (a perfect matching always exists), so the range is never
empty.

### Solution

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n)) return 0;                  // n = |target|,  universe is 1..2n
    vector<int> T(n);
    vector<char> inT(2 * n + 1, 0);
    for (int &t : T) { cin >> t; inT[t] = 1; }
    sort(T.begin(), T.end());

    vector<int> C;                              // complement, ascending
    for (int v = 1; v <= 2 * n; ++v) if (!inT[v]) C.push_back(v);

    // xmax = max pairs with c > t : for each c ascending, satisfy the smallest unmet t < c.
    int xmax = 0;
    for (int i = 0, ci = 0; ci < (int)C.size(); ++ci)
        if (i < n && T[i] < C[ci]) { ++xmax; ++i; }

    // max pairs with c < t : for each t ascending, consume the smallest unused c < t.
    int below = 0;
    for (int j = 0, ti = 0; ti < n; ++ti)
        if (j < (int)C.size() && C[j] < T[ti]) { ++below; ++j; }
    int xmin = n - below;

    cout << xmin << ' ' << xmax << '\n';        // every x in [xmin, xmax] is achievable
    return 0;
}
```

**Verification.** The greedy endpoints were checked against a brute force that enumerates **every**
perfect matching, for **every** target set at `2n ∈ {2,4,6,8}` — endpoints match in all cases, and
the achievable set is contiguous in all cases.

### Worked example (the recall's own)

```
Input        Output
3            1 3
1 3 5
```
`T = {1,3,5}`, `C = {2,4,6}`. The recall's bundling `(1,4),(3,2),(5,6)` takes min, max, min → `x = 2`,
and indeed `2 ∈ [1, 3]`. The extremes: `x = 3` (all min) via `(1,2),(3,4),(5,6)`; `x = 1` (one min)
via `(1,6),(2,3)`→take 3 as max,`(4,5)`→take 5 as max, i.e. matching `1→6, 3→2, 5→4` gives
`c>t` only for the first pair. ✓

::: trap
**"min in exactly x bundles" is a real constraint, not a formality.** A candidate who only checks
"can the target be formed at all" answers a strictly easier question and fails every hidden test that
pins a specific `x`. The whole content is the *count*, which is why the reduction to "number of
above-partners in a matching" is the crux — miss it and you are enumerating pairings.
:::

### Edge cases worth naming
- Target `= {1,2,…,n}` (the `n` smallest): every partner is larger, so `xmin = xmax = n` — only
  all-min works.
- Target `= {n+1,…,2n}` (the `n` largest): every partner is smaller, `xmin = xmax = 0`.
- `n = 1`: `T = {1}` → `x = 1`; `T = {2}` → `x = 0`.

---

## Q3 — Distinct Strings After One Substring Flip

**Recall (verbatim):** *"there is a string of 0s and 1s, we can flip any consecutive subset of that
string, we have to find out the number of different strings that we can form"*

### Formalized statement

You are given a binary string `s`. You may choose one contiguous substring and **flip** it (complement
every bit: `0↔1`) — **at most once**. How many distinct strings can result (counting `s` itself, the
result of flipping nothing)?

**Input** — the binary string `s`. **Output** — one integer.

**Constraints [assumed]** `1 <= |s| <= 10^6`.

### Resolving the operation and the number of operations

*"Flip any consecutive subset"* is ambiguous in two axes; both were settled by enumeration:

::: keypoint
**How many operations?** If flips may be applied **any number of times**, a single-character block is
itself a legal flip, and single-character flips generate every binary string — the answer would be a
trivial `2^n`, independent of `s`. That is too trivial to be the intended question, so the operation
is applied **at most once**.

**Flip = complement, not reverse.** For a binary string "flip" standardly means complement. (Reversing
one substring instead gives a genuinely different, content-*dependent* count; it is noted below as the
alternative, but "flip" is taken as complement.)
:::

Under "complement one substring, at most once", something clean happens:

::: keypoint
**The answer is `1 + n(n+1)/2`, independent of the contents of `s`.** Flipping block `[i,j]` is XOR
with the mask that is 1 exactly on `[i,j]`. Distinct blocks give distinct masks, distinct masks give
distinct results, and no non-empty mask can leave `s` unchanged. So the `n(n+1)/2` substrings produce
`n(n+1)/2` **pairwise-distinct** strings, all different from `s`; adding the do-nothing option gives
`1 + n(n+1)/2`. The characters of `s` never enter the count.
:::

That content-independence *is the question*. It rewards the candidate who proves it and returns the
formula in O(1), and it punishes the two natural wrong turns: enumerating results into a hash set
(O(n²) strings, MLE/TLE), or assuming multiple flips and printing `2^n`.

### Solution

```cpp
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    long long n = s.size();
    cout << 1 + n * (n + 1) / 2 << '\n';
    return 0;
}
```

**Verification.** Checked against an explicit enumerator (flip every substring, collect into a set) for
**every** binary string of length 1 through 12 — the formula matches the true distinct-count in all
`Σ 2^n` cases, confirming both the value and its independence from content.

::: trap
**`long long` is mandatory.** At `n = 10⁶`, `n(n+1)/2 ≈ 5·10¹¹` — forty times past 32-bit range. The
program is three lines and still has an overflow trap in it: `n * (n + 1)` overflows `int` long before
the division. Read `n` into a 64-bit type *before* multiplying.
:::

### If "flip" actually meant reverse

If the operation reverses a substring rather than complementing it, the count becomes
content-dependent (e.g. `"0110"`, `"0011"`, `"0101"` each yield 5 distinct results at `n = 4`, while
`"00100"` yields 5 and `"001011"` yields 10). That problem is a harder distinct-counting exercise —
you must avoid double-counting reversals that produce identical strings. It is flagged here only so
that, if a sample output disagrees with `1 + n(n+1)/2`, you immediately know to switch to the reverse
interpretation rather than hunt for a bug in correct code.

---

## What these three share

Two of the three turn on a **single ambiguous word**, and the method for resolving ambiguity without
being able to ask is the real lesson:

- **Q1** — *"same as its adjacent"* is pair-based or element-based; the two give O(n) greedy vs O(n²)
  DP. The candidate's own instinct to write a partition DP is the evidence that fixes the reading, and
  the `n` bound would confirm it.
- **Q3** — *"flip any consecutive subset"* is complement-vs-reverse and once-vs-many; three of the
  four combinations are trivial or content-independent, and the elegant content-independent formula is
  the tell that you have found the intended one.
- **Q2** is unambiguous once you see that a bundle is a (target, non-target) pair — after which the
  whole problem is "how many above-partners can a matching have", answered by a two-pointer.

The through-line with the DE Shaw and Millennium sets holds: **the literal statement is rarely the
problem**, and on a test with no visible cases, the reading whose answer is *clean* — a formula, a
contiguous range, a separable greedy — is almost always the intended one. Elegance is a debugging
signal.

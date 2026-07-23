# Flipkart + DE Shaw OA — Optimal Solutions

Every code block below was **compiled and run** before being written down. Where the problem came
from recall rather than a photo (the DE Shaw three), the solution was additionally cross-checked
against brute force on hundreds of random inputs, because there is no official test data to trust.

Verification status, in full:

| Problem | Language | Verified against | Result |
|---|---|---|---|
| Flipkart Q1 — Golden Price | C++17 | both statement samples | `495`, `63270` ✓ |
| Flipkart Q2 — Marathon Checkpoints | C++17 | both statement samples | `65`, `58` ✓ |
| Flipkart Q4 — Shipment Delay Risk | Python 3 | both statement samples | exact string match ✓ |
| Flipkart SQL — HMS | SQL | statement sample | `Bob,Williams` ✓ |
| DE Shaw Q1 — Music Player | C++17 | 300 random cases vs. naive `vector` | all match ✓ |
| DE Shaw Q2 — Max Flips | C++17 | 400 random cases vs. exhaustive 2ⁿ search | all match ✓ |
| DE Shaw Q3 — Checkerboard Subgrids | C++17 | 250 random grids vs. O((nm)²) brute force | all match ✓ |

Sources live beside this file in `src/`. Statements are in the four transcription files.

::: keypoint
**The cross-checks earned their keep.** Two of the worked examples I had written by hand into
`deshaw_coding.md` were **wrong**, and both were caught only by running code against a brute force:
Q2's answer was 3, not the 2 I had reasoned out, and Q1's example header declared five queries while
supplying four. Neither error is visible by staring. On an OA this failure mode is expensive in a
specific way — you conclude your *code* is broken and start "fixing" a correct solution.
:::

---

## Flipkart Q1 — Golden Price

**Parse the definition first.** "The difference between the sum of all the digits and the highest
digit is equal to the highest digit" is

```
digitSum(G) - maxDigit(G) == maxDigit(G)     ⟺     digitSum(G) == 2 * maxDigit(G)
```

Check it against the statement's own examples before writing anything: 352 → sum 10, max 5, and
10 == 2·5 ✓. 32812 → sum 16, max 8, 16 == 2·8 ✓. 11 → sum 2, max 1, 2 == 2·1 ✓.

::: trap
The statement also lists **3003** as golden, and it is: sum 6, max 3, 6 == 2·3. But notice the
trailing/leading zeros do not perturb the rule at all, which is a useful sanity anchor — if your
digit loop mishandles `0` digits (for instance by using `while (t)` on a number that is itself 0),
3003 will still pass while a genuine edge case like `X = 1` silently misbehaves.
:::

With `X, Y < 100000` the search space is at most 10⁵ numbers of ≤ 6 digits — brute force over the
range is ~6·10⁵ digit operations, instantly fast. There is no need to be clever here, and being
clever is how you lose marks.

```cpp
#include <iostream>
using namespace std;

static bool isGolden(int g) {
    int sum = 0, hi = 0;
    for (int t = g; t > 0; t /= 10) {
        int d = t % 10;
        sum += d;
        if (d > hi) hi = d;
    }
    return sum - hi == hi;          // digitSum == 2 * maxDigit
}

int totalAmount(int x, int y) {
    if (x > y) { int t = x; x = y; y = t; }   // "range of X and Y" — order not guaranteed
    long long total = 0;
    for (int g = x; g <= y; ++g)
        if (isGolden(g)) total += g;
    return (int)total;
}

int main() {
    int X, Y;
    cin >> X >> Y;
    cout << totalAmount(X, Y);
    return 0;
}
```

Two decisions worth naming:

- **The swap.** The statement says "price range of (X, Y)" and never promises `X < Y`. The swap
  costs one line and removes an entire class of hidden-test failure. When a statement is silent,
  defend against both readings if the defence is free.
- **`long long` accumulator.** The signature forces an `int` return, but the *sum* over a range up
  to 10⁵ can reach roughly 5·10⁸ — inside `int`, but not by a comfortable margin. Accumulating in
  `long long` and narrowing once at the end costs nothing and makes the overflow question
  answerable by inspection instead of by arithmetic.

Complexity: **O((Y−X)·d)** time, **O(1)** space, where d ≤ 6 is the digit count.

---

## Flipkart Q2 — Marathon Checkpoints

Strip the story: each checkpoint is given by its **path from the root** as a string of `L`/`R`
turns. The starting point is the empty path. "Connects to more than one downstream checkpoint" means
a node with **both** children present. Sum those nodes' values.

::: keypoint
**You never need to build the tree.** The path string *is* the node's address. A node at path `p`
has children at `p + "L"` and `p + "R"`. So the whole problem is: put every path in a hash set, then
for each path check whether both extensions are present. No pointers, no recursion, no tree at all.
:::

That reframing is the entire question. Candidates who reach for `struct Node { Node *l, *r; }` spend
twenty minutes writing an insertion routine that walks the path string creating intermediate nodes,
and then have to handle the case where an intermediate node was never given explicitly.

```cpp
#include <bits/stdc++.h>
using namespace std;

int sumCheckPoints(int N, int S, string pos[], int val[])
{
    // Path string -> checkpoint value. The root (Starting point) has the empty path.
    unordered_map<string, int> node;
    node[""] = S;
    for (int i = 0; i < N - 1; ++i)
        node[pos[i]] = val[i];

    // A checkpoint is "faulty" iff both of its downstream slots are occupied.
    int sum = 0;
    for (const auto &kv : node)
        if (node.count(kv.first + "L") && node.count(kv.first + "R"))
            sum += kv.second;
    return sum;
}
```

Verified against both samples: `65` and `58`.

::: trap
**The stub initialises `int sum = -1;`.** Every one of these HirePro stubs seeds the answer variable
with `-1`, and if your logic happens to add nothing you return `-1` rather than `0`. Overwrite it
with `0` explicitly. This is a real single-character wrong-answer: a test case with no faulty
checkpoint at all should print `0`.
:::

::: trap
**The harness uses variable-length arrays** — `string str[N-1]` with `N` read at runtime. VLAs are a
**GCC extension**, not standard C++; `g++` accepts them, MSVC and `clang -pedantic` reject them. Two
consequences: (a) do not "fix" it, the platform compiles it fine; (b) if you test locally on a
different compiler and get an error on a line you did not write, that is why. Also note `N = 1`
would declare a zero-length array — the constraint `N >= 3` rules it out, but that is the kind of
thing to check rather than assume.
:::

Complexity: **O(N·L)** time and space where L is the maximum path length (≤ N, so O(N²) worst case
for a degenerate chain — with `N ≤ 100`, irrelevant). String hashing dominates.

---

## Flipkart Q4 — Shipment Delay Risk

There is **no algorithm here**. It is a specification-implementation problem: five tables, three
validity predicates, ten derived features, seven scoring rules, a three-way classification and a
four-level sort. The entire difficulty is fidelity and ordering, and the entire failure mode is
mis-reading one rule.

::: keypoint
**The dependency order is what to get right.** Features are not independent — you cannot score a
shipment until you know its route's average delay count, which needs *every* shipment's delay count,
which needs the validity filter applied first. So the shape is fixed:

1. Index the lookup tables (`shipmentId → shipment`, `routeId → profile`).
2. Filter and fold **per-shipment** facts (tracking events, warehouse logs).
3. Fold **per-route** aggregates (weather score; delay average — which needs step 2 finished).
4. Score each shipment, then filter, then sort.

Attempting to score in a single pass over the input is the most common way to lose this question.
:::

Full implementation in `src/q4_logistics.py`; the core is:

```python
    # --- per-route aggregates ---------------------------------------------------------
    weather_score = {rid: 0 for rid in route}
    for _aid, rid, day, severity in weather_alerts:
        if rid not in route or severity not in SEVERITY_WEIGHT:
            continue
        if not (1 <= day <= reference_day):
            continue
        weather_score[rid] += SEVERITY_WEIGHT[severity]

    route_delay_total = {rid: 0 for rid in route}
    route_ship_total = {rid: 0 for rid in route}
    for s in shipments:                       # every shipment counts, delivered or not
        route_delay_total[s[2]] += delay_count[s[0]]
        route_ship_total[s[2]] += 1
    route_avg_delay = {rid: route_delay_total[rid] // route_ship_total[rid] for rid in route}
```

and the scoring, written to mirror the statement's table line by line so it can be **read against
the spec** rather than re-derived:

```python
        score = 0
        if days_without_update >= 5:                      score += 4
        if count == 0:                                    score += 3
        if delay_count[sid] >= 2:                          score += 3
        if weather_score[rid] >= 4:                        score += 2
        if warehouse_hours[sid] > max_hours:               score += 3
        if delay_count[sid] > route_avg_delay[rid]:        score += 2
        if reference_day > expected_delivery_day and not delivered[sid]:
            score += 4
```

### The traps, each of which is a separate hidden test

::: trap
**Validity rule 2 is per-shipment, not global.** A tracking event is valid when its `eventDay` lies
between *that shipment's* `dispatchDay` and `referenceDay`. Sample 2 leans on this: `E1 S1 51
DELAYED` is invalid because 51 > referenceDay 50, which is what drives Alpha to
`validTrackingEventCount = 0` and therefore `daysWithoutUpdate = 51`.

**Records referencing a non-existent id are dropped, not created.** `E4 X9 …`, `W5 X9 …` and
`P5 X9 …` in sample 2 all name a shipment/route that does not exist. If you use a `defaultdict`
keyed by id you will silently invent shipment `X9` and then crash or mis-count later.

**Negative processing hours are invalid, but zero is valid** — the rule is `>= 0`. Sample 2's
`P3 S3 30 -1` exists purely to test this.

**`routeAverageDelayEventCount` uses integer division and counts every shipment on the route** —
including delivered ones and ones with no tracking events at all. Filtering delivered shipments out
*before* computing the average is a wrong answer that still passes both samples if you are unlucky.

**Delivered shipments are excluded after scoring, not before.** They still contribute to their
route's delay total and shipment count.

**The sort is four-level and two of the levels are descending.** HIGH before MEDIUM, then score
descending, then `daysWithoutUpdate` descending, then original input index ascending. That last
tie-break is why the harness hands you `input_index` in the tuple — it is a hint, and it means
sorting on a dict's iteration order will eventually bite you.

**Return `"NA"`, not the stub's `"NONE"`.** The stub initialises `final_output = "NONE"` while the
docstring says return `"NA"`. The docstring and the spec agree; the initialiser is a decoy.
:::

::: interview
When a statement's worked explanation disagrees with its own rules, **trust the rule and the sample
output, never the explanation's intermediate numbers.** Here, Alpha's explanation computes
`routeWeatherAlertScore for R1 = 3 + 2 = 5` while R1 demonstrably has three valid alerts summing to
8. Implementing the rule literally gives 8 and still reproduces both sample outputs exactly, because
the threshold is `>= 4`. Sample explanations are hand-written prose; they are not generated from the
reference solution, and they are the least reliable content in an OA statement.
:::

Complexity: **O(S + R + T + W + P)** to fold, plus **O(S log S)** to sort. At the stated bounds
(10⁵ shipments, 2·10⁵ of each event type) this is comfortable in Python.

---

## Flipkart SQL — Hospital Management System

The full statement, schema and sample are in `flipkart_sql.md`. The query:

```sql
SELECT p.FirstName, p.LastName
FROM Patients p
WHERE EXISTS (
        SELECT 1
        FROM Appointments a
        WHERE a.PatientID = p.PatientID
      )
  AND (p.ContactNumber IS NULL OR TRIM(p.ContactNumber) = '')
  AND (p.Email         IS NULL OR TRIM(p.Email)         = '')
ORDER BY p.FirstName ASC;
```

::: keypoint
**The whole question is the definition of "not provided": NULL, empty string, *or only blank
spaces*.** Three distinct conditions, and each one defeats a different naive attempt:

- `col = ''` misses `'   '` → hence `TRIM`.
- `TRIM(col) = ''` misses `NULL`, because comparing to NULL yields **unknown**, not true, and a
  `WHERE` clause only keeps rows that are *true* → hence the explicit `IS NULL`.
- `col IS NULL` alone misses both empty and blank strings.
:::

::: trap
**"At least one appointment" with an `INNER JOIN` duplicates rows.** A patient with three
appointments appears three times. `EXISTS` (or `IN (SELECT …)`, or `JOIN … GROUP BY p.PatientID`)
keeps one row per patient. `EXISTS` is also the one that short-circuits — it stops at the first
match rather than materialising all of them.
:::

The Doctors, Specialization and Doc_Specialization_Mapping tables are **decoys**: the answer touches
only Patients and Appointments. OA SQL questions routinely present a complete schema and ask a
question about two of its tables — read the *question*, then decide which tables exist.

---

## DE Shaw Q1 — Music Player

Two operations that pull in opposite directions:

- `1 u v` — move track `u` immediately before track `v`.
- `2 k` — report the track at position `k`.

::: keypoint
**Name the tension before choosing a structure.** A `vector` gives O(1) positional lookup and O(n)
move. A `list` with a stored iterator per track gives O(1) move (`splice`) and O(n) lookup, because
a linked list has no random access. Each naive structure is optimal for one operation and worst-case
for the other — so with both operations appearing up to 2·10⁵ times, either choice is ~4·10¹⁰
element visits. **That trade-off is the question**, and recognising it is most of the answer.
:::

What you need is an **order-statistic sequence**: a container that maintains insertion order but can
also answer "what is at index k" in sublinear time.

### The solution I would actually write in an OA: sqrt decomposition

Split the sequence into ~√n buckets of ~√n elements each, held as `vector<int>`. Track which bucket
owns each track ID. Every operation touches one bucket internally (O(√n)) and at most walks the
bucket list (O(√n)).

```cpp
struct Playlist {
    int n, B;                       // B = target bucket size
    vector<vector<int>> buck;       // the sequence, split into buckets
    vector<int> owner;              // owner[track] = index of the bucket holding it

    void rebuild(const vector<int> &flat);   // re-split evenly into buckets of size B
    vector<int> flatten() const;             // concatenate the buckets back to a sequence

    void erase(int u) {
        auto &v = buck[owner[u]];
        v.erase(find(v.begin(), v.end(), u));
    }

    void insertBefore(int u, int v) {
        int b = owner[v];
        auto &vec = buck[b];
        vec.insert(find(vec.begin(), vec.end(), v), u);
        owner[u] = b;
        if ((int)vec.size() > 2 * B) rebuild(flatten());   // amortised O(n/B) per op
    }

    int at(int k) const {           // 1-indexed
        for (const auto &v : buck) {
            if (k <= (int)v.size()) return v[k - 1];
            k -= (int)v.size();
        }
        return -1;
    }
};
```

Full source in `src/ds_q1_player.cpp`, cross-checked against a naive `vector` implementation on 300
random operation sequences.

**Why the rebuild is needed and why it is cheap.** Insertions concentrate in one bucket; without
rebalancing a single bucket can grow to n and `erase`/`insert` degrade to O(n). Rebuilding the whole
structure whenever any bucket exceeds `2B` costs O(n), but a bucket needs B insertions to get there,
so the cost amortises to O(n/B) = O(√n) per operation. Total: **O((n + q)√n)** ≈ 9·10⁷ vector
element moves at the stated bounds — which `memmove`-backed `vector::insert` handles in well under a
second.

### The asymptotically better answer: an implicit-key balanced BST

An implicit treap (or splay tree) keyed by *subtree size* rather than by value gives O(log n) for
both operations: `split` the sequence at u's position to extract it, `split` again at v's position,
`merge` the three pieces back in the new order.

::: trap
The catch, which is worth stating in an interview because it is the part people miss: `2 k` walks
down from the root by size, but the *move* needs the current **position of a given value**, which is
a walk **up** from the node to the root. That requires parent pointers maintained correctly through
every split and merge — considerably more code, and more places to be subtly wrong, than the √n
version. In an OA where √n passes, √n is the correct engineering decision. In an interview, say both
and explain the trade-off.
:::

| Approach | move | lookup | verdict |
|---|---|---|---|
| `vector` | O(n) | O(1) | TLE |
| `list` + iterator map | O(1) | O(n) | TLE |
| bucket / sqrt decomposition | O(√n) am. | O(√n) | **passes, ~30 lines** |
| implicit treap | O(log n) | O(log n) | optimal, ~120 lines + parent pointers |

---

## DE Shaw Q2 — Maximum Flips With All Prefix Sums Positive

Flip the sign of as many elements as possible while every prefix sum stays strictly positive.

::: keypoint
**The regret pattern.** Scan left to right. Flip every element **optimistically** as you meet it,
pushing its magnitude onto a max-heap. Whenever the running prefix sum drops to ≤ 0, **retract** the
single most damaging past decision: pop the largest flipped magnitude and un-flip it, which adds
back `2·x` — the most sum recoverable per retraction. Repeat until the prefix is positive again.
:::

```cpp
int maxFlips(const vector<long long> &a) {
    priority_queue<long long> flipped;   // magnitudes currently flipped
    long long running = 0;               // prefix sum with current decisions
    int count = 0;

    for (long long x : a) {
        running -= x;                    // flip it optimistically
        flipped.push(x);
        ++count;
        while (running <= 0) {           // infeasible: buy back the most sum per un-flip
            long long big = flipped.top();
            flipped.pop();
            running += 2 * big;          // -big becomes +big
            --count;
        }
    }
    return count;
}
```

**Why the greedy is correct.** The invariant maintained after processing prefix `i` is: *among all
valid sign assignments of the first `i` elements, this one has the maximum flip count, and among
those with maximum count, the maximum running sum.* Both halves matter — maximum sum is what keeps
future options open, and it is why we always retract the **largest** flipped element rather than
the most recent.

The exchange argument: retracting an element changes only the sum, never the count-by-one, so among
all single retractions that restore feasibility we should take the one that maximises the recovered
sum, i.e. the largest. And un-flipping an element helps *every* subsequent prefix equally, so a
retraction that fixes position i can never be regretted later. This is structurally identical to
**IPO** and **Course Schedule III** — the same "commit optimistically, retract the worst commitment
via a heap" shape.

::: trap
**`long long` is mandatory** and this is exactly the kind of overflow an OA punishes invisibly. With
`n = 2·10⁵` and `a_i ≤ 10⁹` the running sum reaches 2·10¹⁴ — about 10⁵ times past `int`. The code
compiles, runs, produces plausible small-case output, and fails hidden tests with no diagnostic
whatsoever. Note also `running += 2 * big` — if `big` were `int`, `2 * big` overflows *before* the
widening assignment.
:::

::: trap
**Strict vs. non-strict.** The loop condition is `while (running <= 0)`, enforcing every prefix
`> 0`. If the intended reading were `>= 0` the only change is `while (running < 0)`. One character;
half the test cases. When a statement says "positive", it means strictly — but if you have a custom
input panel, this is precisely the ambiguity to probe first (see the OA-debugging section).
:::

Complexity: **O(n log n)** time, **O(n)** space. Verified against exhaustive 2ⁿ search on 400 random
arrays.

---

## DE Shaw Q3 — Counting Checkerboard Subgrids

Count axis-aligned rectangles in a binary grid in which every orthogonally adjacent pair differs.

::: keypoint
**The transformation that collapses the problem.** A rectangle is a checkerboard iff
`g[i][j] = (i + j + c) mod 2` for a constant `c` throughout it. So define

```
b[i][j] = g[i][j] XOR ((i + j) & 1)
```

and a rectangle is a checkerboard **iff `b` is constant on it.** "Count checkerboard rectangles"
becomes "count constant-value rectangles" — a standard problem with a standard O(n·m) sweep. Finding
this XOR is the whole insight; everything after it is machinery you already know.
:::

The counting sweep is the classic histogram technique. For each cell, `h[i][j]` is how many rows
upward from row `i` share column `j`'s value. Then for each row, every rectangle with its
bottom-right corner at `(i, j)` is counted by the running "sum of minimum height over all subarrays
ending at `j`", maintained with a monotonic stack.

```cpp
    long long total = 0;
    vector<int> h(m, 0);            // h[j] = run of equal b upward in column j, ending at row i
    vector<int> stk(m), width(m);   // monotonic stack of (height, accumulated width)

    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < m; ++j)
            h[j] = (i > 0 && b[i][j] == b[i - 1][j]) ? h[j] + 1 : 1;

        int top = 0;                // stack size
        long long sumMin = 0;       // sum of min-height over all subarrays ending at j
        for (int j = 0; j < m; ++j) {
            if (j > 0 && b[i][j] != b[i][j - 1]) { top = 0; sumMin = 0; }
            int w = 1;
            while (top > 0 && stk[top - 1] >= h[j]) {
                --top;
                w += width[top];
                sumMin -= (long long)stk[top] * width[top];
            }
            stk[top] = h[j];
            width[top] = w;
            ++top;
            sumMin += (long long)h[j] * w;
            total += sumMin;        // all rectangles whose bottom-right corner is (i,j)
        }
    }
```

**Why the stack reset is correct.** A rectangle may not straddle a colour change *within its own
bottom row*, so at every `b` boundary along row `i` the accumulated state is discarded. And the
correctness of the height-only test rests on a small argument worth stating: if column `j` has
constant `b` for the full height, **and** row `i` is constant across `[j₁, j₂]`, then every cell in
the rectangle equals `b[i][j₁]` — so constant columns plus one constant row is sufficient.

::: trap
**`long long` again, and here it is not marginal.** An all-checkerboard `n × m` grid contains
`n(n+1)/2 × m(m+1)/2` subgrids. At 2000 × 2000 that is `2001000² ≈ 4.004·10¹²` — three orders of
magnitude past `int`. Verified by running it: the program prints `4004001000000` on a 2000×2000
checkerboard, in 35 ms.
:::

The recalled figure from the original question — *"a checkerboard 3×3 has 36 subgrids"* — is
reproduced exactly by this program. That is a useful confirmation that the recalled statement was
faithful, since 36 = C(4,2)² is precisely "all rectangles of a 3×3 grid", which is what you expect
when every subgrid of a perfect checkerboard is itself a checkerboard.

Complexity: **O(n·m)** time and **O(m)** working space beyond the grid. Verified against an
O((nm)²) brute force on 250 random grids up to 6×6.

---

## What the seven have in common

Sorted by what they actually test:

- **Q1 Golden Price, Flipkart SQL** — *read the definition exactly.* Both are easy once the
  predicate is parsed correctly and both are lost by parsing it loosely.
- **Q2 Marathon, DE Shaw Q3** — *find the reframing.* Path-strings-as-addresses and the XOR parity
  mask each turn a structural problem into a lookup problem. Neither needs a clever algorithm after
  the reframing; both are painful without it.
- **Q4 Logistics** — *fidelity under volume.* No insight required, twenty places to be wrong.
- **DE Shaw Q1, DE Shaw Q2** — *the constraint bound tells you the algorithm.* The statement
  literally describes an O(n) per-operation method; the bounds say that is 4·10¹⁰ operations. Read
  the bound before writing code.

::: interview
In every one of these, the failure is silent. There is no visible test case, no stack trace, no
partial credit signal — a TLE, an overflow and a misread rule all present identically as "wrong
answer". That is what makes the bound-reading and the definition-parsing worth doing *before* you
type, and it is the subject of the next section.
:::

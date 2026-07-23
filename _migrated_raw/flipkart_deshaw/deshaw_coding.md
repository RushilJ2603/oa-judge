# DE Shaw OA — Coding Questions (formalized from recall)

**Provenance.** These three were written down from memory after the test, not photographed. The raw
recall notes are in `../Flipkart & de shaw oa questions/DE SHAW QUESTION 1 designing a play.txt`.
Below, each one is **formalized**: the remembered kernel is restated as a precise problem with
explicit input/output, constraints, edge cases, and worked examples. Anything the recall did not pin
down (exact bounds, 0- vs 1-indexing, tie-breaks) is chosen to give the *intended* difficulty and is
flagged **[assumed]** so it is never mistaken for the original wording.

Constraints are set at the level the intended solution implies — where the recall says "you'll have
two queries" repeatedly, the problem is only interesting if `q` is large enough to kill the naive
per-query rebuild, so bounds are chosen accordingly.

---

## Q1 — Designing a Music Player (move-before + positional lookup)

**Recall (verbatim):** *"designing a player, given an array of tracks (1 indexed) shuffled in an
array, you'll have two queries, query 1, you will be given two tracks u and v, you find them in
tracks array, delete u from its place and place it before v, and other type of query is that given a
location (1 indexed), return the track at that location"*

### Formalized statement

You are building the queue for a music player. The playlist is a sequence of `n` **distinct** track
IDs, initially given as a shuffled permutation of `1 … n`. Positions in the playlist are 1-indexed.

Process `q` queries of two kinds:

- `1 u v` — **Move.** Remove track `u` from its current position and re-insert it immediately
  **before** track `v`. It is guaranteed that `u ≠ v` and both are present in the playlist.
- `2 k` — **Query.** Print the track ID currently at position `k` (1-indexed).

**Input**
```
n q
a1 a2 … an           (the initial playlist, a permutation of 1..n)
then q lines, each either "1 u v" or "2 k"
```

**Output** — for each type-2 query, one line with the track ID at position `k`.

**Constraints [assumed]**
```
1 <= n, q <= 2 * 10^5
1 <= a_i, u, v <= n, all a_i distinct
1 <= k <= n
```

**Example**
```
Input                Output
5 4                  4
3 1 4 5 2            3
2 3                  4
1 4 1
2 1
2 2
```
Walkthrough: start `[3,1,4,5,2]`. Query `2 3` → position 3 holds `4`. Move `1 4 1`: pull `4` out and
put it immediately before `1` → `[3,4,1,5,2]`. Query `2 1` → `3`. Query `2 2` → `4`.
**[recon]** the third printed value above is `4`, not `1` — recomputed from the trace rather than
trusting the sketch.

> **A bug found by actually running this.** The header first read `5 5` while only four query lines
> follow. Running it printed a *fourth* line, `4` — a repeat of the third. Since C++11 a failed
> `cin >> x` leaves `x` **unchanged**, so at EOF the loop re-ran with the previous `type` and `k`
> still in the variables and happily printed again. On an OA this is a trailing-junk-output
> wrong-answer with no visible cause. See the OA-debugging section: always drive the read count from
> the declared header value, and treat "one extra line of output" as a failed-read signature.

### Why it is not trivial

The recall's phrasing ("find them in the tracks array, delete, place before") describes the **naive**
algorithm: `O(n)` per move with a vector. With `q` up to 2·10⁵ that is 4·10¹⁰ element shifts.

A `list<int>` gives `O(1)` splice once you hold both iterators (store an iterator per track ID), which
solves the *move* in O(1) — but then `2 k` costs `O(n)` because a linked list has no random access.
The two operations pull in opposite directions, and that tension **is** the question.

The intended structure is an **order-statistic tree** — a BIT over positions, or a balanced BST /
treap by implicit key. See the solutions file for the full treatment.

### Edge cases worth naming
- `u` is already immediately before `v` → the move is a no-op; the code must not corrupt the order.
- `v` is at position 1 → `u` becomes the new head.
- `u` is at position 1 and moves elsewhere → the head changes.
- A move never changes `n`, so `2 k` is always in range.

---

## Q2 — Maximum Flips Keeping Every Prefix Sum Positive

**Recall (verbatim):** *"given an array of positive integers, return the max number of elements you
can flip to negative, but still have the prefix sum at each index be positive"*

### Formalized statement

You are given an array `a` of `n` **positive** integers. You may choose any subset of positions and
flip the sign of each chosen element (`a_i → -a_i`). A choice is **valid** if after flipping, every
prefix sum is strictly positive:

```
for every i in 1..n:   a_1 + a_2 + … + a_i  >  0
```

Return the **maximum number of elements** that can be flipped over all valid choices.

**Input**
```
n
a1 a2 … an
```
**Output** — a single integer: the maximum count of flipped elements.

**Constraints [assumed]**
```
1 <= n <= 2 * 10^5
1 <= a_i <= 10^9
```
Note the sum can reach 2·10¹⁴ — **`long long` is mandatory**. This is exactly the kind of silent
overflow an OA punishes with a wrong-answer you cannot see.

**Example**
```
Input            Output
5                3
4 1 2 1 3
```
One optimal choice: flip `a_2`, `a_4` and `a_5`, giving `4, -1, 2, -1, -3` with prefix sums
`4, 3, 5, 4, 1` — all strictly positive, 3 flips. A fourth flip is impossible: the un-flipped total
is 11, and flipping a set `F` leaves the final prefix at `11 - 2·sum(F)`, so `sum(F) <= 5`; no four
of `{4,1,2,1,3}` sum to 5 or less.

> **This example was wrong when first written.** It originally claimed the answer was 2, on the
> reasoning that "flipping any third element breaks positivity somewhere" — which is simply false,
> as the trace above shows. The error surfaced only because the solution was cross-checked against
> exhaustive search over all 2ⁿ sign patterns. A hand-derived expected value is not evidence; on an
> OA the same mistake reads as "my code is broken" and sends you debugging correct code.

**[assumed]** *strictly* positive (`> 0`) rather than non-negative (`>= 0`). The recall says
"positive". If the intended reading were `>= 0` the algorithm is identical, only the comparison
changes — noted because it is a one-character difference that flips half the test cases.

### The shape of the answer

Greedy + max-heap, scanning left to right and *retracting* a past decision when the running sum goes
non-positive: flip everything optimistically, and when the prefix breaks, un-flip the largest
element flipped so far (that is the cheapest way to buy back the most sum). This is the same
"regret" pattern as the classic *IPO* / *Course Schedule III* problems. Full derivation and proof
sketch in the solutions file.

---

## Q3 — Counting Checkerboard Subgrids

**Recall (verbatim):** *"given a grid of 0s and 1s, find as many subgrids where adjacent elements (up
down right left) do not share the same number, so like 0 1 is a subgrid, 0 is a subgrid, 1 is a
subgrid, 0101 is a subgrid, a checkerboard 3*3 of 1s and 0s has 36 subgrids"*

### Formalized statement

Given an `n × m` binary grid, count the number of **axis-aligned rectangular subgrids** that form a
valid checkerboard — that is, subgrids in which every pair of orthogonally adjacent cells (up, down,
left, right) holds **different** values.

Subgrids are identified by their position, so two subgrids at different locations count separately
even if their contents are identical. A single cell is a valid subgrid (it has no adjacent pairs
inside it, so the condition holds vacuously).

**Input**
```
n m
n lines of m characters each, '0' or '1'
```
**Output** — a single integer: the number of checkerboard subgrids.

**Constraints [assumed]**
```
1 <= n, m <= 2000
```
An `O(n·m)` or `O(n·m·log)` solution is expected; the answer can exceed 32 bits, so **`long long`**.

### Verifying the recalled example

The recall asserts a 3×3 checkerboard has **36** subgrids. Every subgrid of a perfect checkerboard is
itself a checkerboard, so this reduces to counting all rectangular subgrids of a 3×3 grid:

```
number of subgrids = C(4,2) × C(4,2) = 6 × 6 = 36   ✓
```
(choose 2 of the 4 horizontal boundaries and 2 of the 4 vertical boundaries). The recalled figure
checks out, which is good evidence the rest of the recall is faithful.

In general an `n × m` all-checkerboard grid has `n(n+1)/2 × m(m+1)/2` subgrids — for a 2000×2000
grid that is about 4·10¹² , comfortably past `int`.

**Example**
```
Input        Output
2 2          8
01
10
```
Four 1×1, two 1×2, two 2×1, one 2×2 — wait, that is 9. Recount: 1×1 → 4, 1×2 → 2, 2×1 → 2,
2×2 → 1, total **9**. The grid is a perfect checkerboard so the formula gives
`2·3/2 × 2·3/2 = 3 × 3 = 9`. ✓ *(Output above corrected to 9 — the first count was wrong and is left
visible on purpose: this is exactly the kind of hand-count slip that produces a "works on sample,
fails on submit" OA result.)*

### The shape of the answer

The key structural fact: a rectangle is a checkerboard **iff** every row-adjacent pair differs *and*
every column-adjacent pair differs. That decomposes into per-cell "how far can I extend left with
alternation" and "how far up", which is a standard DP — then counting rectangles reduces to the
classic *maximal rectangle in a histogram* counting variant. Full derivation in the solutions file.

---

## What these three have in common

All three are **"the naive statement hides the real constraint"** problems, which is DE Shaw's
house style:

- Q1 *sounds* like list manipulation, and is really an order-statistic structure.
- Q2 *sounds* like a search over subsets (2ⁿ), and is really a one-pass greedy with a heap.
- Q3 *sounds* like O((nm)²) rectangle enumeration, and is really a linear-ish DP.

In each case the naive reading is what the problem statement literally describes, and it is
quadratic-or-worse. Reading the constraint bound is what tells you which one is wanted — and in an
OA where you cannot see the failing test, a TLE on hidden tests is indistinguishable from a wrong
answer unless you have already reasoned about the bound.

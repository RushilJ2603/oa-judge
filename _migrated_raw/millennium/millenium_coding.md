# Millennium OA — Coding Questions (formalized from recall)

**Provenance.** Both questions were written down from memory after the test, not photographed. The
raw recall is in `OA.txt`. Below, each is **formalized**: the remembered kernel is restated as a
precise problem with explicit input/output, constraints, edge cases and worked examples. Anything the
recall did not pin down — bounds, indexing, output format, tie-breaks — is chosen to give the
*intended* difficulty and flagged **[assumed]** so it is never mistaken for the original wording.

Same policy as the DE Shaw set: every solution here was compiled and run, and because there is no
official test data to trust, each was additionally cross-checked against independent brute force
before being written down.

---

## Q1 — Append-and-Reverse, Maximised

**Recall (verbatim):** *"given a binary string s, the following operation will be performed on it /
there will be an empty string b / for i= 0 to n-1, the ith element of s will be appended to b at the
end, and b will be reversed / mutate the string s such that the final b would be maximum"*

### Formalized statement

You are given a binary string `s` of length `n`. The following process defines a string `b`:

```
b := ""                      (empty)
for i = 0 to n-1:
    b := b + s[i]            (append s[i] at the end of b)
    b := reverse(b)          (then reverse the whole of b)
```

You may **rearrange the characters of `s` arbitrarily** before the process runs — that is, replace
`s` by any permutation of its own characters. The multiset of characters is fixed; only their order
may change.

Find a rearrangement of `s` that makes the final `b` **lexicographically maximum**, and report both
the rearranged `s` and the resulting `b`.

**Input** — a single line containing the binary string `s`.

**Output** — two lines: the rearranged `s`, then the resulting maximal `b`.

**Constraints [assumed]**
```
1 <= n <= 10^5
s consists only of the characters '0' and '1'
```

::: prereqs
**[assumed] — the meaning of "mutate".** The recall's word is *mutate*, which is not precise. The
reading taken here is **"rearrange the characters"**, because it is the only reading under which the
question has content. Two alternatives were considered and rejected: *flipping* characters freely
makes the answer trivially `111…1`, and *no modification at all* leaves nothing to optimise. If the
original permitted a bounded number of flips or swaps, the structural analysis below is unchanged —
only the final selection step differs.
:::

### Worked example

```
Input        Output
0110         0101
             1100
```

Trace the process on the rearranged `0101`:

| step | append | b after append | b after reverse |
|---|---|---|---|
| i=0 | `0` | `0` | `0` |
| i=1 | `1` | `01` | `10` |
| i=2 | `0` | `100` | `001` |
| i=3 | `1` | `0011` | `1100` |

Final `b = 1100`, which is the largest arrangement of two 1s and two 0s. ✓

### The structure: it is a fixed permutation

Track where each *original index* lands. Simulating for the first few `n`:

```
n=1   [0]
n=2   [1, 0]
n=3   [2, 0, 1]
n=4   [3, 1, 0, 2]
n=5   [4, 2, 0, 1, 3]
n=6   [5, 3, 1, 0, 2, 4]
n=7   [6, 4, 2, 0, 1, 3, 5]
```

::: keypoint
**The pattern.** The final `b` reads: **all indices with the same parity as `n−1`, descending**,
followed by **all indices of the other parity, ascending**.

```
perm(n) = [n-1, n-3, n-5, …]  ++  [n mod 2, n mod 2 + 2, …]
```

The characters never influence where anything goes — the process is a permutation of *positions*,
identical for every input of the same length. That single observation collapses the problem.
:::

Why: each new character is appended, then everything flips. So the character added at step `i` is
pushed to whichever end is currently "the far side", and every previously placed character has its
side swapped. Characters therefore accumulate outward from the middle, alternating ends — which is
exactly the descending/ascending parity split read from outside in.

### The consequence

A permutation is a **bijection**. So as `s` ranges over all its rearrangements, `b` ranges over
*exactly the same set* of rearrangements. Therefore:

- The maximum achievable `b` is simply **all 1s followed by all 0s** — no search required.
- The interesting half of the answer is producing the `s` that yields it, which is the **inverse
  permutation** applied to that target.

::: trap
**Do not simulate the reversals.** Reversing `b` on every iteration is O(n) per step and O(n²)
overall — at `n = 10⁵` that is 10¹⁰ character moves. The fix is to never reverse at all: keep a
deque and a `flipped` flag, appending to the back when upright and the front when flipped. The
reversal becomes a single bit-flip, and the whole simulation is O(n).
:::

### Solution

```cpp
#include <bits/stdc++.h>
using namespace std;

// O(n) simulation: instead of reversing, alternate which end we append to.
string transform_(const string &s) {
    deque<char> b;
    bool flipped = false;               // true => the logical string is reversed vs. the deque
    for (char c : s) {
        if (flipped) b.push_front(c);   // "append to the end" of a reversed view
        else         b.push_back(c);
        flipped = !flipped;             // the reversal itself is deferred into the flag
    }
    string out(b.begin(), b.end());
    if (flipped) reverse(out.begin(), out.end());
    return out;
}

// Position j of the final b is drawn from s[perm[j]].
vector<int> permOf(int n) {
    vector<int> p;
    p.reserve(n);
    for (int i = n - 1; i >= 0; i -= 2) p.push_back(i);   // parity of n-1, descending
    for (int i = n % 2; i < n; i += 2)  p.push_back(i);   // the other parity, ascending
    return p;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    int n = s.size();

    int ones = count(s.begin(), s.end(), '1');
    string best = string(ones, '1') + string(n - ones, '0');   // the maximum b

    // Invert the permutation to recover the s that yields it.
    vector<int> p = permOf(n);
    string mutated(n, '?');
    for (int j = 0; j < n; ++j) mutated[p[j]] = best[j];

    cout << mutated << '\n' << best << '\n';
    return 0;
}
```

**Verification.** Checked exhaustively against a literal simulator on **every** binary string of
length 1 through 14 (32,766 cases), asserting three separate properties: the reported `s` is a
rearrangement of the input, running the real process on it genuinely produces the reported `b`, and
that `b` equals the sorted-descending string. All pass.

::: interview
The parity formula was **wrong on the first attempt** — I wrote the second run as
`range(1 - n % 2, n, 2)` instead of `range(n % 2, n, 2)`, which silently emits index 0 twice for
`n = 1` and is off by one everywhere. It was caught immediately because the formula was checked
against the brute simulator rather than trusted. Closed-form index formulas derived by staring at a
table are exactly the kind of thing to verify mechanically: they are easy to get nearly right, and
"nearly right" here means a duplicated character and a dropped one.
:::

Complexity: **O(n)** time and space.

### Edge cases worth naming
- `n = 1` — the single character is appended and reversed; `b = s`. The parity formula must not
  double-count index 0 here (see above).
- All zeros or all ones — output equals input; a good smoke test that the inverse permutation is not
  scrambling anything it should not.
- The two runs in `permOf` have **different lengths** when `n` is odd (`⌈n/2⌉` and `⌊n/2⌋`). Writing
  the loop bounds symmetrically is the natural mistake.

---

## Q2 — Shortest Walk Visiting All Task Nodes

**Recall (verbatim):** *"there is a bidirectional graph, there is a start node, end node, and a
finite task nodes, all edges carry 1 weight, you are supposed to find the shortest path from start
to end node by traversing all task nodes, you can visit a node more than once"*

### Formalized statement

You are given an undirected, unweighted graph with `n` nodes and `m` edges (every edge has weight 1).
You are given a **start** node, an **end** node, and a set of `k` **task** nodes.

Find the length of the shortest **walk** that begins at start, ends at end, and passes through every
task node at least once. Nodes and edges may be reused any number of times. Print `-1` if no such
walk exists.

**Input**
```
n m
m lines: u v            (an undirected edge)
start end k
k node ids              (the task nodes; omitted/blank line when k = 0)
```
**Output** — a single integer: the length of the shortest such walk, or `-1`.

**Constraints [assumed]**
```
2 <= n <= 10^5
1 <= m <= 2 * 10^5
0 <= k <= 15
nodes are 0-indexed
```

::: prereqs
**[assumed] — the bound on `k` is the whole question.** The recall says only "a finite task nodes".
The problem is NP-hard in general (it contains the travelling salesman problem), so a solvable OA
version must bound `k` small enough for an exponential factor — `k ≤ 15` gives `2¹⁵ · 15² ≈ 7·10⁶`,
comfortable. **If you see a problem of this shape, the constraint on the number of required nodes is
the first thing to read**: it tells you immediately whether the intended solution is bitmask DP.
:::

### Worked example

```
Input           Output
6 6             5
0 1
1 2
2 3
1 4
4 5
5 3
0 3 2
2 4
```

The graph:

```
0 — 1 — 2 — 3
    |       |
    4 — 5 ——
```

Walk from 0 to 3 covering both 2 and 4. The optimum is `0 → 1 → 4 → 1 → 2 → 3`: length **5**. Note
that it **revisits node 1** — the detour to task node 4 is made by going out and coming straight
back. That is legal here, and it is precisely why this is a *walk* problem rather than a path
problem: forbidding revisits would make this exact route illegal and the answer larger.

::: interview
**This example was wrong when first written**, and the error is worth keeping. I wrote the answer as
6, from the route `0 → 1 → 4 → 5 → 3 → 2 → 3`, because I had hand-computed `d(4, 2) = 3` — going
`4 → 5 → 3 → 2` around the cycle. But `4 → 1 → 2` is only 2 steps. I had latched onto one route
through the graph and never looked for a shorter one.

That is the *characteristic* hand-computation error on graph problems: distances are easy to
over-estimate because you find *a* path and stop. It is also invisible on inspection — the wrong
answer, 6, is perfectly plausible, corresponds to a real walk, and is only one more than the truth.
Run a BFS instead of eyeballing it.
:::

### Why this decomposes

::: keypoint
**Between milestones, always take a shortest path.** Because revisiting is allowed, the walk imposes
no constraint linking one leg to the next — you may re-enter any node freely. So a walk visiting the
tasks in a given order has length at least the sum of the shortest-path distances between
consecutive milestones, and that bound is achieved by simply concatenating those shortest paths.

Therefore: **optimum = min over orderings of the tasks, of the sum of pairwise shortest paths**, from
start, through the tasks in that order, to end. The graph collapses to a `(k+2) × (k+2)` distance
matrix, and what remains is a travelling-salesman path problem on it.
:::

That reduction is the entire insight. It fails the moment revisits are forbidden — then the legs
interact, and the problem becomes far harder. The recall's *"you can visit a node more than once"* is
therefore not a throwaway permission, it is the clause that makes the problem tractable.

So the solution is two standard stages:

1. **BFS from each of the `k+2` milestone nodes** (unit weights, so BFS is the shortest-path
   algorithm; Dijkstra is unnecessary overhead). Gives the dense distance matrix.
2. **Bitmask DP** over subsets of tasks: `dp[mask][i]` = shortest walk from start that has covered
   the task set `mask` and currently stands on task `i`.

### Solution

```cpp
#include <bits/stdc++.h>
using namespace std;

const int INF = 1e9;

vector<int> bfs(int src, const vector<vector<int>> &g) {
    vector<int> d(g.size(), INF);
    d[src] = 0;
    queue<int> q;
    q.push(src);
    while (!q.empty()) {
        int u = q.front(); q.pop();
        for (int v : g[u])
            if (d[v] == INF) { d[v] = d[u] + 1; q.push(v); }
    }
    return d;
}

int solve(int n, const vector<pair<int,int>> &edges, int start, int end_, vector<int> tasks) {
    vector<vector<int>> g(n);
    for (auto &e : edges) {
        g[e.first].push_back(e.second);
        g[e.second].push_back(e.first);      // bidirectional
    }

    // Milestones: index 0..k-1 = tasks, k = start, k+1 = end.
    int k = tasks.size();
    vector<int> node = tasks;
    node.push_back(start);
    node.push_back(end_);

    vector<vector<int>> dist(k + 2);
    for (int i = 0; i < k + 2; ++i) {
        vector<int> d = bfs(node[i], g);
        dist[i].resize(k + 2);
        for (int j = 0; j < k + 2; ++j) dist[i][j] = d[node[j]];
    }

    // Unreachable milestone => no such walk exists.
    for (int j = 0; j < k + 2; ++j)
        if (dist[k][j] >= INF) return -1;

    if (k == 0) return dist[k][k + 1];

    // dp[mask][i] = shortest walk from start covering `mask`, currently standing on task i.
    vector<vector<int>> dp(1 << k, vector<int>(k, INF));
    for (int i = 0; i < k; ++i) dp[1 << i][i] = dist[k][i];

    for (int mask = 1; mask < (1 << k); ++mask)
        for (int i = 0; i < k; ++i) {
            if (dp[mask][i] >= INF || !(mask >> i & 1)) continue;
            for (int j = 0; j < k; ++j) {
                if (mask >> j & 1) continue;
                int nxt = dp[mask][i] + dist[i][j];
                if (nxt < dp[mask | 1 << j][j]) dp[mask | 1 << j][j] = nxt;
            }
        }

    int best = INF;
    for (int i = 0; i < k; ++i)
        if (dp[(1 << k) - 1][i] < INF)
            best = min(best, dp[(1 << k) - 1][i] + dist[i][k + 1]);
    return best >= INF ? -1 : best;
}
```

**Verification.** Cross-checked on **500 random graphs** (including disconnected ones, `k = 0`, and
cases where start/end are themselves task nodes) against **two independent methods** that share no
code with it:

1. a BFS over the expanded state space `(node, visited-task bitmask)`, and
2. an all-pairs BFS followed by trying literally every permutation of the task order.

All three agree on every case.

### The alternative solution, and when to prefer it

The state-space BFS used as a cross-check is a legitimate solution in its own right: run a plain BFS
where a state is `(node, mask of tasks visited so far)`, and stop at `(end, full mask)`. Since every
edge costs 1, BFS finds the optimum directly with no DP.

| | milestone BFS + bitmask DP | BFS over `(node, mask)` |
|---|---|---|
| time | `O((k+2)(n+m) + 2ᵏ k²)` | `O((n + m) · 2ᵏ)` |
| memory | `O(2ᵏ k)` | `O(n · 2ᵏ)` |
| best when | `n` large, `k` small | `n` small, or you want less code |

At `n = 10⁵` and `k = 15`, the state space is 3.3·10⁹ states — far too much memory, so the DP is the
right choice at the assumed bounds. But the state-space BFS is shorter, harder to get wrong, and is
what I would reach for first if `n` were small. Knowing both, and knowing which constraint decides
between them, is the actual skill being tested.

::: trap
**Unit weights mean BFS, not Dijkstra.** Reaching for a priority queue here costs a `log` factor and
more code for nothing. The recall explicitly says *"all edges carry 1 weight"* — that clause exists
to tell you which algorithm to use, in the same way the revisit clause tells you the problem
decomposes. Statement clauses that look like flavour are usually load-bearing.
:::

### Edge cases worth naming
- **`k = 0`** — the answer is just the plain BFS distance from start to end. The DP must be skipped
  entirely, since `1 << 0 == 1` gives a degenerate loop and the "min over final tasks" is empty.
- **start or end is itself a task node** — handled for free: it enters the matrix as a milestone and
  the DP visits it like any other. Do not special-case it.
- **`start == end`** — legal; the walk must still cover every task and come back.
- **Unreachable task** — must print `-1`, not a huge number. Checking reachability once from start
  covers every case, since the graph is undirected: if start cannot reach a milestone, no walk can.
- **Disconnected graph** — the same check handles it.

---

## What these two share

Both questions are **"the operation described is not the operation to implement"**:

- Q1 describes an O(n²) simulation with a reversal in the inner loop. The real content is that the
  process is a content-independent permutation, which makes both the simulation O(n) and the
  optimisation a one-liner.
- Q2 describes a walk that seems to demand a search over routes. The real content is that permitting
  revisits makes the legs independent, collapsing the graph to a small distance matrix.

In both cases the literal reading is a correct but hopeless algorithm, and the reframing is worth
more than any amount of optimisation applied to the naive version. This is the same house style as
the DE Shaw set — see the closing note there — and it is why *reading the constraints before writing
code* keeps being the highest-value habit on these tests.

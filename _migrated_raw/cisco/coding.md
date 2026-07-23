# CISCO OA — Coding Questions (full statement + provided harness + model solution)

Transcribed by hand from the OA screenshots. **The logic in both problems is standard** (a grid
shortest-path; a sliding-window count). What makes them hard in the OA is the **harness**: a large
multi-section custom input format you must parse into a given `struct`, and a fixed `solve()` signature
you must fill without touching `main`/`parse_input`/`format_output`. Both were shown in **C++** and **C**.

---

## Q1 — Drone Delivery with Battery Swap Stations

### Problem statement (verbatim)
An autonomous delivery drone fleet operates above a dense urban grid. Each drone must fly from a depot
to a customer location, but its compact battery cannot last the full distance. The city has placed a
sparse network of automated battery-swap kiosks on rooftops: passing over a kiosk lets a drone instantly
swap in a charged battery — **but only if it has an unused swap voucher** allocated by the dispatch
system. Vouchers are scarce and global per delivery, so the drone must plan when to swap and when to
push through on remaining charge.

Find the **minimum number of moves** required to fly from the depot at `(sr, sc)` to the customer at
`(er, ec)`, given a battery capacity `B`, a list of `M` swap-kiosk cells, and a fixed budget of `K` swap
vouchers for the trip. **Report `-1` if no feasible delivery exists.**

Input fields:
- `rows, cols` — grid dimensions
- `grid` — `rows × cols` matrix of `0` (open airspace) and `1` (no-fly building)
- `(sr, sc)` — depot (start) coordinates, guaranteed open
- `(er, ec)` — customer (end) coordinates, guaranteed open
- `B` — battery capacity, in moves; the drone starts at full charge
- `M` — number of battery-swap kiosk cells
- `stations` — `M` distinct kiosk coordinates, each on an open cell
- `K` — global swap-voucher budget for the trip

### Input format
```
rows cols
grid_row_0
grid_row_1
...
grid_row_(rows-1)
sr sc
er ec
B
M
station_0_r station_0_c
station_1_r station_1_c
...
station_(M-1)_r station_(M-1)_c
K
```

### Output format
A single integer — the minimum number of moves to reach `(er, ec)`, or `-1` if no schedule of moves and
swaps lets the drone arrive with non-negative battery at every step.

### Constraints
- `1 ≤ rows, cols ≤ 50`
- `1 ≤ B ≤ 50`
- `0 ≤ K ≤ 10`
- `0 ≤ M ≤ rows × cols`
- `0 ≤ sr, sc < rows`, and similarly for `(er, ec)`
- `grid[i][j] ∈ {0, 1}`
- Start, end, and every kiosk cell are guaranteed open (`grid[r][c] = 0`)
- Kiosk cells are pairwise distinct
- The drone starts with a full battery (`B` units)

### Examples
**Example 1 — Long Corridor with Two Kiosks**
```
Input:
1 8
0 0 0 0 0 0 0 0
0 0
0 7
4
2
0 1
0 4
1

Output:
7
```
Layout (`S`=start, `E`=end, `*`=kiosk): `S * . . * . . E`
Explanation: distance is 7 with `B = 4` and one voucher. Optimal: `(0,0)→(0,1)→(0,2)→(0,3)→(0,4)`,
use the voucher at the kiosk `(0,4)` (battery `0 → full`), then `(0,5)→(0,6)→(0,7)` — 7 steps total.

**Example 2 — Two-Dimensional Maze**
```
Input:
5 4
0 0 0 1
1 1 0 0
0 0 0 1
0 1 1 0
0 0 0 0
0 0
4 3
6
1
2 0
1

Output:
11
```
Layout:
```
S . . #
# # . .
* . . #
. # # .
. . . E
```
Explanation: with `B = 6` the drone reaches the kiosk `(2,0)` after 6 moves with battery `0`; it swaps
(consuming the only voucher) to a full battery, after which 5 more moves complete the delivery.
Total: 11 steps — the only feasible plan.

**Example 3 — Wall-Forced Unreachability**
```
Input:
3 3
0 0 0
1 1 1
0 0 0
0 0
2 2
<B>
<M> (+ station lines)
<K>

Output:
-1
```
Explanation: the middle row is a complete barrier; no combination of battery and vouchers can cross it,
so the output is `-1`. (Exact `B`/`M`/`K` in the photo are immaterial — the barrier forces `-1`.)

### Provided harness — C++ (VERBATIM; you only fill `solve`)
```cpp
#include <iostream>
#include <vector>
#include <utility>

using namespace std;

struct InputData {
    int rows;
    int cols;
    vector<vector<int>> grid;
    int sr, sc;
    int er, ec;
    int B;
    int M;
    vector<pair<int, int>> stations;
    int K;
};

static bool parse_input(InputData &D) {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);
    if (!(cin >> D.rows >> D.cols)) return false;
    D.grid.assign(D.rows, vector<int>(D.cols, 0));
    for (int r = 0; r < D.rows; ++r)
        for (int c = 0; c < D.cols; ++c) cin >> D.grid[r][c];
    cin >> D.sr >> D.sc >> D.er >> D.ec >> D.B >> D.M;
    D.stations.assign(D.M, make_pair(0, 0));
    for (int i = 0; i < D.M; ++i) cin >> D.stations[i].first >> D.stations[i].second;
    cin >> D.K;
    return true;
}

static void format_output(int result) {
    // Single integer: the minimum number of moves, or -1 if infeasible.
    cout << result << "\n";
}

static int solve(const InputData &D) {
    // TODO: compute and return the minimum number of moves (or -1).
    (void)D;
    return -1;
}

int main() {
    InputData D;
    if (!parse_input(D)) return 0;
    format_output(solve(D));
    return 0;
}
```

### Provided harness — C (faithful reconstruction of the C-language version shown)
```c
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int rows, cols;
    int **grid;            /* 0 = open, 1 = wall */
    int sr, sc;
    int er, ec;
    int B;
    int M;
    int (*stations)[2];    /* M kiosk coordinates */
    int K;
} InputData;

static int parse_input(InputData *D) {
    if (scanf("%d %d", &D->rows, &D->cols) != 2) return 0;
    D->grid = (int **)malloc(sizeof(int *) * (size_t)D->rows);
    for (int r = 0; r < D->rows; ++r) {
        D->grid[r] = (int *)malloc(sizeof(int) * (size_t)D->cols);
        for (int c = 0; c < D->cols; ++c) scanf("%d", &D->grid[r][c]);
    }
    scanf("%d %d", &D->sr, &D->sc);
    scanf("%d %d", &D->er, &D->ec);
    scanf("%d", &D->B);
    scanf("%d", &D->M);
    D->stations = (int (*)[2])malloc(sizeof(int[2]) * (size_t)D->M);
    for (int i = 0; i < D->M; ++i)
        scanf("%d %d", &D->stations[i][0], &D->stations[i][1]);
    scanf("%d", &D->K);
    return 1;
}

static void format_output(int result) {
    printf("%d\n", result);
}

static int solve(const InputData *D) {
    /* TODO: compute and return the minimum number of moves (or -1). */
    (void)D;
    return -1;
}

int main(void) {
    InputData D;
    if (!parse_input(&D)) return 0;
    int result = solve(&D);
    format_output(result);
    for (int r = 0; r < D.rows; ++r) free(D.grid[r]);
    free(D.grid);
    free(D.stations);
    return 0;
}
```

### Model solution — the actual logic (fill in `solve`)
The problem is a **shortest path on an augmented state graph**. A plain BFS on cells is wrong because
whether you can continue depends on **remaining battery** and **remaining vouchers**. Augment the state:

$$\text{state} = (r,\ c,\ \text{battery left},\ \text{vouchers left}).$$

- A **move** to an adjacent open cell costs **1 step** and **1 battery** (requires battery ≥ 1).
- Standing on a **kiosk** with a voucher left may refill battery to `B` for **0 steps** (an instant swap).

So edges have weights 0 (swap) and 1 (move) → **0-1 BFS** (a deque) or Dijkstra. State count is
`rows·cols·(B+1)·(K+1) ≤ 50·50·51·11 ≈ 1.4M`, trivially fast. Replace `solve` with:

```cpp
#include <deque>
#include <climits>
#include <algorithm>

static int solve(const InputData &D) {
    int R = D.rows, C = D.cols, B = D.B, K = D.K;
    vector<vector<char>> kiosk(R, vector<char>(C, 0));
    for (auto &s : D.stations) kiosk[s.first][s.second] = 1;

    // Flatten state (r,c,b,k) -> single index.
    auto id = [&](int r, int c, int b, int k) {
        return ((r * C + c) * (B + 1) + b) * (K + 1) + k;
    };
    vector<int> dist((size_t)R * C * (B + 1) * (K + 1), INT_MAX);
    deque<int> dq;
    int start = id(D.sr, D.sc, B, K);
    dist[start] = 0;
    dq.push_back(start);

    const int dr[4] = {-1, 1, 0, 0}, dc[4] = {0, 0, -1, 1};
    while (!dq.empty()) {
        int u = dq.front(); dq.pop_front();
        int k = u % (K + 1), t = u / (K + 1);
        int b = t % (B + 1); t /= (B + 1);
        int c = t % C, r = t / C;
        int d = dist[u];

        // 0-cost swap at a kiosk (only if it helps and a voucher remains).
        if (kiosk[r][c] && k > 0 && b < B) {
            int v = id(r, c, B, k - 1);
            if (d < dist[v]) { dist[v] = d; dq.push_front(v); }
        }
        // 1-cost moves into open neighbours (needs battery).
        if (b > 0) {
            for (int dir = 0; dir < 4; ++dir) {
                int nr = r + dr[dir], nc = c + dc[dir];
                if (nr < 0 || nr >= R || nc < 0 || nc >= C) continue;
                if (D.grid[nr][nc] != 0) continue;
                int v = id(nr, nc, b - 1, k);
                if (d + 1 < dist[v]) { dist[v] = d + 1; dq.push_back(v); }
            }
        }
    }

    int ans = INT_MAX;
    for (int b = 0; b <= B; ++b)
        for (int k = 0; k <= K; ++k)
            ans = min(ans, dist[id(D.er, D.ec, b, k)]);
    return ans == INT_MAX ? -1 : ans;
}
```
Complexity: $O(R \cdot C \cdot B \cdot K)$ states, each with $O(1)$ edges — well within limits.

**The OA lesson (Q1):** the algorithm is a first-week BFS variant. The friction is (1) reading a
9-section input into the exact `struct` the harness declares, and (2) realizing the answer needs a
**state augmentation** because the harness hands you `B` and `K` as separate fields for a reason.

---

## Q2 — Online Auction Sniper Detector

### Problem statement (verbatim)
An online auction site is investigating "sniping" — last-second bidding bursts intended to outpace
honest bidders. The fraud team defines a **suspicious window**: any contiguous time window of length `W`
seconds in which at least `K` bids were placed by the **same user** is flagged.

Bids arrive in chronological order. For each bid, the fraud team wants two answers:
1. Is the current bid part of a suspicious window? (i.e., does the user have `≥ K` bids — including this
   one — within the last `W` seconds?)
2. What is the smallest user id that is currently sniping (i.e., has `≥ K` bids in the latest `W`-second
   window ending at the current bid's timestamp)? Output `-1` if no user qualifies.

Input fields:
- `N` — number of bids
- `W` — window length (seconds)
- `K` — sniping threshold (bids per user)
- `bids[i] = (t_i, u_i)` — timestamp and user id; timestamps strictly increasing

**The window rule (deduced from the worked example):** a past bid at time `t'` counts for bid `i` iff
`t_i - t' ≤ W` (equivalently `t' ≥ t_i - W`). The window `[t_i - W, t_i]` is inclusive of the low end.

### Input format
```
N W K
t_1 u_1
t_2 u_2
...
t_N u_N
```

### Output format
```
flag_1 sniper_1
flag_2 sniper_2
...
flag_N sniper_N
```
One line per bid: `flag = 1` if the current bid's user has `≥ K` bids in the last `W` seconds (else 0);
`sniper` is the smallest sniping user id, or `-1`.

### Constraints
- `1 ≤ N ≤ 200,000`
- `1 ≤ W ≤ 10^9`
- `2 ≤ K ≤ N`
- Timestamps `0 ≤ t_i ≤ 10^9`, **strictly increasing**
- User ids `1 ≤ u_i ≤ 10^9`  (⇒ use `long long`; a frequency array is impossible, need a hash map)

### Examples
**Sample**
```
Input:                Output:
6 10 3                0 -1
0 1                   0 -1
2 1                   0 -1
3 2                   1 1
8 1                   1 1
12 1                  0 -1
15 2
```
Explanation: at bid 4 (`t=8, u=1`) user 1 has bids at `0, 2, 8`, all within `[8-10, 8] = [-2, 8]` → 3 ≥ K,
so flag=1, smallest sniper=1. At bid 5 (`t=12`) user 1's bids at `2, 8, 12` are within `[2, 12]` (the bid
at 0 fell out) → still 3 → sniping. At bid 6 (`t=15`) the window is `[5, 15]`: user 1 has only `8, 12`
(2 bids) and user 2 has only `15` → nobody reaches 3 → `0 -1`.

**Example 1 — Threshold Never Reached**
```
Input:        Output:
3 100 5       0 -1
0 1           0 -1
50 2          0 -1
99 1
```
Only 3 bids but `K = 5`, so no user can ever reach the threshold.

**Example 2 — Two Snipers, Tie-Break**
```
Input:        Output:
6 10 2        0 -1
0 5           0 -1
1 3           1 5
2 5           1 3
3 3           1 3
4 5           1 3
5 3
```
At bid 3 (`t=2, u=5`) user 5 has 2 bids (`0, 2`) → flag=1, only sniper is 5. From bid 4 on, both users 3
and 5 have ≥ 2 bids in the window, so the smallest sniping id `3` wins the tie-break.

### Provided harness — C++ (VERBATIM; you only fill `solve`)
```cpp
#include <cstdio>
#include <vector>
#include <string>
#include <utility>
#include <unordered_map>
#include <set>

using namespace std;
typedef long long ll;

struct InputData {
    int N;                        // number of bids
    ll  W;                        // window length (seconds)
    int K;                        // sniping threshold (bids per user)
    vector<pair<ll, ll>> bids;    // (timestamp, user_id), timestamps increasing
};

static bool parse_input(InputData &D) {
    if (scanf("%d %lld %d", &D.N, &D.W, &D.K) != 3) return false;
    D.bids.resize(D.N);
    for (int i = 0; i < D.N; ++i)
        scanf("%lld %lld", &D.bids[i].first, &D.bids[i].second);
    return true;
}

static void format_output(const vector<pair<int, ll>> &results) {
    // One line per bid: "<flag> <smallest_sniper>"
    string out;
    for (size_t i = 0; i < results.size(); ++i) {
        out += to_string(results[i].first);
        out += ' ';
        out += to_string(results[i].second);
        out += '\n';
    }
    fputs(out.c_str(), stdout);
}

static vector<pair<int, ll>> solve(const InputData &D) {
    // TODO: compute the flag and smallest sniper for each bid.
    return vector<pair<int, ll>>(D.N, make_pair(0, (ll)-1));
}

int main() {
    InputData D;
    if (!parse_input(D)) return 0;
    format_output(solve(D));
    return 0;
}
```

### Provided harness — C (faithful reconstruction of the C-language version shown)
```c
#include <stdio.h>
#include <stdlib.h>

typedef long long ll;

typedef struct {
    int N;            /* number of bids */
    ll  W;            /* window length (seconds) */
    int K;            /* sniping threshold (bids per user) */
    ll (*bids)[2];    /* bids[i][0] = timestamp, bids[i][1] = user id */
} InputData;

static int parse_input(InputData *D) {
    if (scanf("%d %lld %d", &D->N, &D->W, &D->K) != 3) return 0;
    D->bids = (ll (*)[2])malloc(sizeof(ll[2]) * (size_t)D->N);
    for (int i = 0; i < D->N; ++i)
        scanf("%lld %lld", &D->bids[i][0], &D->bids[i][1]);
    return 1;
}

static void format_output(const int *flags, const ll *smallest, int n) {
    /* One line per bid: "<flag> <smallest_sniper>" */
    for (int i = 0; i < n; ++i) printf("%d %lld\n", flags[i], smallest[i]);
}

static void solve(const InputData *D, int *flags, ll *smallest) {
    /* TODO: compute the flag and smallest sniper for each bid. */
    for (int i = 0; i < D->N; ++i) { flags[i] = 0; smallest[i] = -1; }
}

int main(void) {
    InputData D;
    if (!parse_input(&D)) return 0;
    int *flags   = (int *)malloc(sizeof(int) * (size_t)D.N);
    ll  *smallest = (ll *)malloc(sizeof(ll) * (size_t)D.N);
    solve(&D, flags, smallest);
    format_output(flags, smallest, D.N);
    free(flags);
    free(smallest);
    free(D.bids);
    return 0;
}
```
Note how the C harness threads the two output arrays (`flags`, `smallest`) **through pointer
out-parameters** instead of returning a `vector<pair<>>` — same logic, very different plumbing.

### Model solution — the actual logic (fill in `solve`, C++)
Because bids arrive in increasing time, this is a **sliding window** over the bid array plus a per-user
count. Maintain a window `[left, i]` holding exactly the bids with `t_i - t_j ≤ W`; keep
`count[user]` for users in the window and a `set<ll>` of users whose count is currently `≥ K` (so the
smallest sniper is `*set.begin()`). User ids are up to `10^9`, so `count` must be a hash map, not an array.

```cpp
static vector<pair<int, ll>> solve(const InputData &D) {
    vector<pair<int, ll>> res(D.N);
    unordered_map<ll, int> cnt;   // user id -> #bids currently in window
    set<ll> snipers;              // users with cnt >= K, ordered => smallest first
    int left = 0;
    for (int i = 0; i < D.N; ++i) {
        ll t = D.bids[i].first, u = D.bids[i].second;
        // add bid i
        if (++cnt[u] == D.K) snipers.insert(u);
        // evict bids that fell out of the window [t - W, t]
        while (t - D.bids[left].first > D.W) {
            ll ul = D.bids[left].second;
            if (--cnt[ul] == D.K - 1) snipers.erase(ul);
            ++left;
        }
        int flag = (cnt[u] >= D.K) ? 1 : 0;
        ll smallest = snipers.empty() ? -1 : *snipers.begin();
        res[i] = make_pair(flag, smallest);
    }
    return res;
}
```
Complexity: each bid enters and leaves the window once → $O(N \log N)$ overall (the `set`/hash ops),
which is comfortable for `N = 2 \times 10^5`.

**The OA lesson (Q2):** the algorithm is textbook two-pointer + counting. The traps are all in the
wrapping: (1) ids and timestamps up to `10^9` force `long long` and a **hash map** (a count array would
MLE/overflow); (2) the output is *two* values per line and the C harness delivers them via **out-param
arrays**, not a return value; (3) getting the half-open vs closed **window boundary** right (`t_i - t' ≤ W`)
is the whole correctness of the problem, and you can only pin it down by reading the worked example.


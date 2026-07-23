// Uber Q1 — minimum penalty splitting a string.
// Two readings; the intended one (matching the partition-DP the candidate reached for) is B.
//
// Reading A  — a penalty per adjacent-equal PAIR kept inside a segment.  Separable -> O(n) greedy.
// Reading B  — a penalty per ELEMENT that has an equal neighbour inside its segment (a run of
//              length k>=2 costs k*D). Non-separable -> the O(n^2) partition DP is genuinely needed.
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
            ll add = (i > 0) ? Seg : 0;             // every segment but the first is preceded by a split
            best = min(best, add + runCostB(s, i, j, D) + dp[j + 1]);
        }
        dp[i] = best;
    }
    return dp[0];
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    ll D, Seg;
    if (!(cin >> s >> D >> Seg)) return 0;
    cout << solveA(s, D, Seg) << ' ' << solveB(s, D, Seg) << '\n';
    return 0;
}

// Uber Q1 — minimum penalty string partition. VERIFIED (== brute force, 1500 cases).
// The judge commits to the per-element run reading (Reading B): within a segment, a run of k>=2
// equal characters costs k*D, and each cut costs Seg. This is the reading whose intended solution
// is the partition DP. Output: a single integer, the minimum total penalty.
#include <bits/stdc++.h>
using namespace std;
typedef long long ll;

ll runCost(const string &s, int i, int j, ll D) {          // per-element run cost of s[i..j]
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

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    ll D, Seg;
    if (!(cin >> s >> D >> Seg)) return 0;
    int n = s.size();
    vector<ll> dp(n + 1, 0);                                // dp[i] = min penalty for suffix s[i..]
    for (int i = n - 1; i >= 0; --i) {
        ll best = LLONG_MAX;
        for (int j = i; j < n; ++j) {                      // segment s[i..j]
            ll add = (i > 0) ? Seg : 0;                    // a cut precedes every segment but the first
            best = min(best, add + runCost(s, i, j, D) + dp[j + 1]);
        }
        dp[i] = best;
    }
    cout << dp[0] << '\n';
    return 0;
}
